from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


class ScreenshotInfo(BaseModel):
    path: str
    step: int
    timestamp: str


@router.get("/screenshots/{app}/{task}")
async def get_screenshots(app: str, task: str):
    return {"app": app, "task": task, "screenshots": []}


@router.get("/logs")
async def get_logs():
    return {"logs": []}
