import os
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional, Dict, Any
from utils.logger import get_logger
from utils.helpers import get_screenshot_path, ensure_dir

logger = get_logger(name="browser_automation")


class BrowserController:
    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        timeout: int = 30000,
        viewport_width: int = 1920,
        viewport_height: int = 1080
    ):
        self.headless = headless
        self.browser_type = browser_type
        self.timeout = timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def start(self):
        logger.info("Starting browser automation")
        playwright = await async_playwright().start()
        
        browser_map = {
            "chromium": playwright.chromium,
            "firefox": playwright.firefox,
            "webkit": playwright.webkit
        }
        
        browser_class = browser_map.get(self.browser_type, playwright.chromium)
        self.browser = await browser_class.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={'width': self.viewport_width, 'height': self.viewport_height}
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        logger.info(f"Browser started: {self.browser_type}, headless={self.headless}")
    
    async def navigate(self, url: str):
        if not self.page:
            raise RuntimeError("Browser not started")
        logger.log_action("navigate", {"url": url})
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=self.timeout)
        except Exception as e:
            logger.warning(f"Navigation timeout, trying with domcontentloaded: {e}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
    
    async def click(self, selector: str, timeout: Optional[int] = None):
        if not self.page:
            raise RuntimeError("Browser not started")
        logger.log_action("click", {"selector": selector})
        await self.page.click(selector, timeout=timeout or self.timeout)
    
    async def type(self, selector: str, text: str, delay: int = 100):
        if not self.page:
            raise RuntimeError("Browser not started")
        logger.log_action("type", {"selector": selector, "text_length": len(text)})
        await self.page.fill(selector, text)
    
    async def screenshot(self, app: str, task: str, step: int, full_page: bool = True):
        if not self.page:
            raise RuntimeError("Browser not started")
        screenshot_path = get_screenshot_path(app, task, step)
        ensure_dir(os.path.dirname(screenshot_path))
        await self.page.screenshot(path=screenshot_path, full_page=full_page)
        logger.log_action("screenshot", {"path": screenshot_path, "step": step})
        return screenshot_path
    
    async def wait_for_selector(self, selector: str, timeout: Optional[int] = None):
        if not self.page:
            raise RuntimeError("Browser not started")
        await self.page.wait_for_selector(selector, timeout=timeout or self.timeout)
    
    async def wait_for_load_state(self, state: str = "networkidle"):
        if not self.page:
            raise RuntimeError("Browser not started")
        try:
            await self.page.wait_for_load_state(state, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"Wait for {state} timeout, trying domcontentloaded: {e}")
            await self.page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
    
    async def get_text(self, selector: str) -> str:
        if not self.page:
            raise RuntimeError("Browser not started")
        return await self.page.text_content(selector) or ""
    
    async def get_url(self) -> str:
        if not self.page:
            return ""
        return self.page.url
    
    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")

