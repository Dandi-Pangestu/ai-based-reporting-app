from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from contextlib import asynccontextmanager
from mcp_client import MCPClient
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

# Example: Add your server configs here
SERVER_CONFIGS = {
    "visualization_server": {
        "command": "uv",
        "args": [
            "run",
            "--with",
            "mcp[cli]",
            "mcp",
            "run",
            "/Users/dandipangestu/Documents/Learn/AI/ai-based-reporting-app/mcp_server/visualization_server.py"
        ]
    },
    "postgres": {
        "command": "npx",
        "args": [
          "-y",
          "@modelcontextprotocol/server-postgres",
          "postgresql://postgres:password@localhost:5432/hub_test"
        ]
      }
    # Add more servers here as needed
    # "another_server": { ... }
}

class Settings(BaseSettings):
    server_configs: Dict[str, Dict[str, Any]] = SERVER_CONFIGS

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_client = MCPClient()
    try:
        await mcp_client.connect_to_server(settings.server_configs)
        app.state.mcp_client = mcp_client
        yield
    except Exception as e:
        print(f"Error during lifespan: {e}")
        raise HTTPException(status_code=500, detail="Error during lifespan") from e
    finally:
        await mcp_client.cleanup()

app = FastAPI(title="MCP Client API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

class Message(BaseModel):
    role: str
    content: Any

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]

@app.post("/query")
async def process_query(request: QueryRequest):
    """Process a query and return the response"""
    try:
        messages = await app.state.mcp_client.process_query(request.query)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/tools")
async def get_tools():
    """Get the list of available tools"""
    try:
        # Return all tools from all servers
        return {"tools": app.state.mcp_client.all_tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/servers")
async def list_servers():
    try:
        return {"servers": list(app.state.mcp_client.sessions.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)