from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from contextlib import asynccontextmanager
from mcp_client import MCPClient
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os
import uvicorn

load_dotenv()

# Read Postgres credentials from environment variables
POSTGRES_USER = os.getenv("DATABASE_USERNAME", "postgres")
POSTGRES_PASSWORD = os.getenv("DATABASE_PASSWORD", "password")
POSTGRES_HOST = os.getenv("DATABASE_HOST", "localhost")
POSTGRES_PORT = os.getenv("DATABASE_PORT", "5432")
POSTGRES_DB = os.getenv("DATABASE_NAME", "hub_test")
POSTGRES_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Define visualization server path
VISUALIZATION_SERVER_PATH = os.getenv("VISUALIZATION_SERVER_PATH", "/to/path/to/visualization_server.py")

# Define the server configurations
SERVER_CONFIGS = {
    "visualization_server": {
        "command": "uv",
        "args": [
            "run",
            "--with",
            "mcp[cli]",
            "mcp",
            "run",
            VISUALIZATION_SERVER_PATH
        ]
    },
    "postgres": {
        "command": "npx",
        "args": [
          "-y",
          "@modelcontextprotocol/server-postgres",
          POSTGRES_URL
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
    uvicorn.run(app, host="0.0.0.0", port=8000)