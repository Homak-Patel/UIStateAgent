from typing import TypedDict, List, Dict, Any, Optional
from utils.logger import get_logger
from utils.browser_controller import BrowserController
from agents.ui_navigator_agent import UINavigatorAgent
from agents.screenshot_agent import ScreenshotAgent
from agents.state_validator_agent import StateValidatorAgent
from agents.context_sync_agent import ContextSyncAgent

logger = get_logger(name="workflow")


class WorkflowState:
    def __init__(self):
        self.task_query: str = ""
        self.app_url: str = ""
        self.app_name: str = ""
        self.task_name: str = ""
        self.navigation_steps: List[Dict[str, Any]] = []
        self.current_step: int = 0
        self.screenshots: List[str] = []
        self.state_valid: bool = True
        self.completed: bool = False
        self.error: Optional[str] = None


class AgentWorkflow:
    def __init__(
        self,
        browser: BrowserController,
        llm_model: str = "gpt-4",
        max_steps: int = 50,
        retry_attempts: int = 3
    ):
        self.browser = browser
        self.llm_model = llm_model
        self.max_steps = max_steps
        self.retry_attempts = retry_attempts
        
        self.navigator = UINavigatorAgent(browser, llm_model)
        self.screenshot = ScreenshotAgent(browser, llm_model)
        self.validator = StateValidatorAgent(browser, llm_model)
        self.context_sync = ContextSyncAgent(llm_model)
    
    async def _navigate_step(self, state: WorkflowState):
        logger.log_action("navigate_step", {"step": state.current_step})
        
        try:
            if state.current_step == 0:
                navigation_steps = await self.navigator.navigate_to_task(
                    state.task_query,
                    state.app_url
                )
                state.navigation_steps = navigation_steps
            
            if state.current_step < len(state.navigation_steps):
                step = state.navigation_steps[state.current_step]
                action_type = step.get("action_type", "click")
                selector = step.get("selector", "")
                
                if action_type == "click":
                    await self.browser.click(selector)
                elif action_type == "type":
                    text = step.get("text", "")
                    await self.browser.type(selector, text)
                elif action_type == "navigate":
                    url = step.get("url", state.app_url)
                    await self.browser.navigate(url)
                
                state.current_step += 1
            else:
                state.completed = True
            
        except Exception as e:
            logger.log_error(e, context={"step": "navigate"})
            state.error = str(e)
            state.completed = True
    
    async def _screenshot_step(self, state: WorkflowState):
        logger.log_action("screenshot_step", {"step": state.current_step})
        
        try:
            screenshot_path = await self.screenshot.capture_screenshot(
                app=state.app_name,
                task=state.task_name,
                step=state.current_step,
                context=state.task_query
            )
            state.screenshots.append(screenshot_path)
        except Exception as e:
            logger.log_error(e, context={"step": "screenshot"})
    
    async def _validate_step(self, state: WorkflowState):
        logger.log_action("validate_step", {"step": state.current_step})
        
        try:
            validation = await self.validator.validate_state()
            state.state_valid = validation.get("valid", False)
            
            if not state.state_valid:
                issues = validation.get("issues", [])
                logger.warning(f"Validation failed: {issues}")
        except Exception as e:
            logger.log_error(e, context={"step": "validate"})
            state.state_valid = False
    
    async def _sync_context_step(self, state: WorkflowState):
        logger.log_action("sync_context_step", {"step": state.current_step})
        
        try:
            workflow_id = f"{state.app_name}_{state.task_name}"
            context_data = {
                "step": state.current_step,
                "screenshots": state.screenshots,
                "state_valid": state.state_valid,
                "url": await self.browser.get_url()
            }
            self.context_sync.sync_context(workflow_id, state.current_step, context_data)
        except Exception as e:
            logger.log_error(e, context={"step": "sync_context"})
    
    def _should_continue(self, state: WorkflowState) -> bool:
        if state.completed or state.error:
            return False
        if state.current_step >= self.max_steps:
            return False
        return True
    
    async def execute(
        self,
        task_query: str,
        app_url: str,
        app_name: str,
        task_name: str
    ) -> Dict[str, Any]:
        logger.log_agent_start("AgentWorkflow", task=task_query)
        
        state = WorkflowState()
        state.task_query = task_query
        state.app_url = app_url
        state.app_name = app_name
        state.task_name = task_name
        
        try:
            while self._should_continue(state):
                await self._navigate_step(state)
                await self._screenshot_step(state)
                await self._validate_step(state)
                await self._sync_context_step(state)
            
            result = {
                "success": state.completed and not state.error,
                "screenshots": state.screenshots,
                "steps_completed": state.current_step,
                "error": state.error,
                "final_url": await self.browser.get_url()
            }
            
            logger.log_agent_end("AgentWorkflow", success=result["success"])
            return result
        except Exception as e:
            logger.log_error(e, context={"workflow": "execute"})
            logger.log_agent_end("AgentWorkflow", success=False)
            return {
                "success": False,
                "screenshots": [],
                "error": str(e)
            }
