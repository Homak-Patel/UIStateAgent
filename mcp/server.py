from fastapi import FastAPI
from typing import Any, Dict, List
import os
from dotenv import load_dotenv
from utils.logger import get_logger
from utils.upstash_sync import UpstashSync

load_dotenv()
logger = get_logger(name="mcp_server")

app = FastAPI(title="MCP Server")


@app.get("/")
async def root():
    return {"message": "MCP Server", "status": "running"}


@app.get("/api/context/{app}/{task}")
async def get_context(app: str, task: str):
    upstash = UpstashSync()
    key = f"{app}_{task}"
    context = upstash.get(key)
    return context or {}


@app.post("/api/context/{app}/{task}")
async def save_context(app: str, task: str, context: Dict[str, Any]):
    upstash = UpstashSync()
    key = f"{app}_{task}"
    import json
    return upstash.set(key, json.dumps(context))


@app.get("/api/apps")
async def list_apps():
    return {"apps": ["notion", "linear", "asana"]}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
