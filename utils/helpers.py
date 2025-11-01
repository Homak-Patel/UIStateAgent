import os
from pathlib import Path
from typing import Dict, Any


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def get_screenshot_path(app: str, task: str, step: int) -> str:
    base_dir = os.getenv('SCREENSHOT_DIR', './data/screenshots')
    ensure_dir(f"{base_dir}/{app}/{task}")
    return f"{base_dir}/{app}/{task}/step_{step:03d}.png"


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.2f}s"
