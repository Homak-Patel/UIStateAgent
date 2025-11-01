from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from utils.logger import get_logger
from utils.browser_controller import BrowserController
from graph.workflow import AgentWorkflow
from utils.helpers import sanitize_filename

# Load .env file - check both mounted path and current directory
env_file = os.getenv("ENV_FILE", ".env")
try:
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)
except (PermissionError, OSError):
    # If we can't access the file directly, try loading from current directory
    load_dotenv(override=True)
logger = get_logger(name="api")

app = FastAPI(title="Agent B API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_dir = Path(__file__).parent.parent / "data"
if data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")


class TaskRequest(BaseModel):
    task_query: str
    app_url: str
    app_name: str
    task_name: Optional[str] = None


class TaskResponse(BaseModel):
    success: bool
    screenshots: List[str]
    steps_completed: int
    error: Optional[str] = None
    final_url: Optional[str] = None


@app.get("/")
async def root():
    return {"message": "Agent B API", "status": "running"}


@app.get("/health")
async def health():
    openai_key = os.getenv("OPENAI_API_KEY")
    return {
        "status": "healthy",
        "openai_configured": bool(openai_key and openai_key.strip())
    }


@app.get("/api/v1/screenshot/{file_path:path}")
async def get_screenshot(file_path: str):
    screenshot_path = data_dir / "screenshots" / file_path
    if screenshot_path.exists() and screenshot_path.is_file():
        return FileResponse(str(screenshot_path))
    raise HTTPException(status_code=404, detail="Screenshot not found")


@app.post("/api/v1/execute", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    logger.info(f"Task request received: {request.task_query}")
    
    # Check for OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or not openai_key.strip():
        error_msg = (
            "OPENAI_API_KEY not found or is empty in environment. "
            "Please ensure your .env file contains: OPENAI_API_KEY=sk-... "
            "(with your actual API key, no spaces around the = sign)"
        )
        logger.error(error_msg)
        logger.debug(f"ENV_FILE={os.getenv('ENV_FILE')}, Current dir={os.getcwd()}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    browser = None
    try:
        browser = BrowserController(
            headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
            browser_type=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
            timeout=int(os.getenv("PLAYWRIGHT_TIMEOUT", "60000")),
            viewport_width=int(os.getenv("PLAYWRIGHT_VIEWPORT_WIDTH", "1920")),
            viewport_height=int(os.getenv("PLAYWRIGHT_VIEWPORT_HEIGHT", "1080"))
        )
        
        await browser.start()
        
        workflow = AgentWorkflow(
            browser=browser,
            llm_model=os.getenv("CREWAI_LLM_MODEL", "gpt-4"),
            max_steps=int(os.getenv("LANGGRAPH_MAX_STEPS", "50")),
            retry_attempts=int(os.getenv("LANGGRAPH_RETRY_ATTEMPTS", "3"))
        )
        
        task_name = request.task_name or sanitize_filename(request.task_query)
        
        result = await workflow.execute(
            task_query=request.task_query,
            app_url=request.app_url,
            app_name=request.app_name,
            task_name=task_name
        )
        
        screenshot_urls = []
        for screenshot_path in result.get("screenshots", []):
            if screenshot_path.startswith("./data/screenshots/"):
                screenshot_urls.append(screenshot_path.replace("./data/screenshots/", ""))
            elif screenshot_path.startswith("data/screenshots/"):
                screenshot_urls.append(screenshot_path.replace("data/screenshots/", ""))
            else:
                screenshot_urls.append(screenshot_path)
        
        result["screenshots"] = screenshot_urls
        
        return TaskResponse(**result)
    
    except Exception as e:
        logger.log_error(e, context={"endpoint": "execute_task"})
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if browser:
            await browser.close()


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
