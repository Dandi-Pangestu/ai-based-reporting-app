from typing import Optional, Dict
from contextlib import AsyncExitStack
import traceback

# from utils.logger import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import datetime
from utils.logger import logger
import json
import os

from anthropic import Anthropic
from anthropic.types import Message


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stacks: Dict[str, AsyncExitStack] = {}
        self.llm = Anthropic()
        self.logger = logger

    # connect to multiple MCP servers
    async def connect_to_server(self, configs: dict):
        """
        Connect to multiple MCP servers using a dict of configs: {server_name: config}
        Build a mapping of tool_name -> server_name for all tools and cache all_tools.
        """
        self.tool_to_server = {}
        self.all_tools = []
        for name, config in configs.items():
            await self._connect_single_server(name, config)
            tools = await self.get_mcp_tools(name)
            for tool in tools:
                self.tool_to_server[tool.name] = name
                self.all_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                })

    async def _connect_single_server(self, name, config):
        try:
            command = config.get("command")
            args = config.get("args", [])
            if not command:
                raise ValueError("Config must include a 'command' key.")
            exit_stack = AsyncExitStack()
            server_params = StdioServerParameters(command=command, args=args, env=None)
            stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()
            self.sessions[name] = session
            self.exit_stacks[name] = exit_stack
            self.logger.info(f"Connected to MCP server '{name}' with command: {command} {args}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to MCP server '{name}': {e}")
            traceback.print_exc()
            raise
        
    # get mcp tool list
    async def get_mcp_tools(self, name):
        try:
            session = self.sessions[name]
            response = await session.list_tools()
            return response.tools
        except Exception as e:
            self.logger.error(f"Error getting MCP tools for '{name}': {e}")
            raise
        
    # cleanup
    async def cleanup(self, name=None):
        try:
            if name:
                await self.exit_stacks[name].aclose()
                del self.sessions[name]
                del self.exit_stacks[name]
                self.logger.info(f"Disconnected from MCP server '{name}'")
            else:
                for n in list(self.sessions.keys()):
                    await self.exit_stacks[n].aclose()
                    self.logger.info(f"Disconnected from MCP server '{n}'")
                self.sessions.clear()
                self.exit_stacks.clear()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()
            raise
        
    # process query
    async def process_query(self, query: str):
        """
        Process a query, and automatically call the correct tool on the correct server
        using the tool_to_server mapping. Uses cached self.all_tools.
        """
        self.logger.info(f"Processing query: {query}")
        user_message = {"role": "user", "content": query}
        messages = [user_message]
        while True:
            response = self.llm.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=messages,
                tools=self.all_tools,
            )
            if response.content[0].type == "text" and len(response.content) == 1:
                assistant_message = {
                    "role": "assistant",
                    "content": response.content[0].text,
                }
                messages.append(assistant_message)
                break
            assistant_message = {
                "role": "assistant",
                "content": response.to_dict()["content"],
            }
            messages.append(assistant_message)
            for content in response.content:
                if content.type == "tool_use":
                    tool_name = content.name
                    tool_args = content.input
                    tool_use_id = content.id
                    server_name = self.tool_to_server.get(tool_name)
                    if not server_name:
                        self.logger.error(f"No server found for tool {tool_name}")
                        continue
                    session = self.sessions[server_name]
                    self.logger.info(f"Calling tool {tool_name} on server {server_name} with args {tool_args}")
                    try:
                        result = await session.call_tool(tool_name, tool_args)
                        self.logger.info(f"Tool {tool_name} result: {result}...")
                        messages.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_use_id,
                                        "content": result.content,
                                    }
                                ],
                            }
                        )
                    except Exception as e:
                        self.logger.error(f"Error calling tool {tool_name}: {e}")
                        raise
        return messages
        
    # call llm
    async def call_llm(self):
        try:
            self.logger.info("Calling LLM")
            return self.llm.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=self.messages,
                tools=self.tools,
            )
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            raise