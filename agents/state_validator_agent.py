from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from typing import Optional, Dict, Any, List
from utils.logger import get_logger
from utils.browser_controller import BrowserController
import time

logger = get_logger(name="state_validator_agent")


class StateValidatorAgent:
    def __init__(self, browser: BrowserController, llm_model: str = "claude-sonnet-4-5-20250929"):
        self.browser = browser
        self.llm = self._get_llm(llm_model)
        self.agent = Agent(
            role="Advanced UI State Validation Specialist",
            goal="Validate UI states with context-awareness - detecting silent failures, regressions, and state inconsistencies",
            backstory="""Expert in comprehensive UI state validation with deep understanding of:
            - Context-aware validation (not just DOM-aware)
            - Silent failure detection (actions that appear successful but don't complete)
            - State transition verification (ensuring state changes are complete)
            - Regression detection (unexpected state changes)
            - Dynamic content validation (SPAs, modals, async operations)
            - Error pattern recognition across different web frameworks""",
            verbose=True,
            llm=self.llm
        )
        # Track state history for regression detection
        self.state_history: List[Dict[str, Any]] = []
        self.validation_count = 0
    
    def _get_llm(self, model: str):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        if "claude" in model.lower():
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            return ChatAnthropic(model=model, api_key=api_key)
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found")
            # Remove temperature parameter entirely for compatibility
            return ChatOpenAI(model=model, api_key=api_key)
    
    async def validate_state(
        self, 
        expected_state: Optional[str] = None,
        previous_action: Optional[str] = None,
        action_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Context-aware state validation that:
        1. Validates current state
        2. Detects silent failures
        3. Checks for state regressions
        4. Verifies state transitions are complete
        """
        logger.log_agent_start("StateValidatorAgent")
        self.validation_count += 1
        
        try:
            # Capture comprehensive state
            current_url = await self.browser.get_url()
            page_text = await self.browser.get_text("body")
            page_html = await self.browser.get_page_html()
            
            # Capture workflow state (URL and non-URL states)
            workflow_state = await self.browser.capture_full_workflow_state()
            
            # Check for modals, forms, errors
            modals = await self.browser.detect_and_handle_modals()
            forms = await self.browser.detect_forms()
            
            # Build context for validation
            context_info = f"""
**Current State Information**:
- Current URL: {current_url}
- State Type: {workflow_state.get('state_type', 'unknown')}
- Modals Detected: {len(modals)} {'(MODAL ACTIVE)' if modals else ''}
- Forms Detected: {len(forms)}
- Page content preview: {page_text[:800]}

**Action Context**:
- Previous Action: {previous_action or 'None'}
- Expected State After Action: {expected_state or 'No specific expectation'}
- Action Details: {action_context if action_context else 'N/A'}

**State History Context**:
- Validation #: {self.validation_count}
- Previous States: {len(self.state_history)} recorded
"""
            
            # Add regression detection context if we have history
            regression_info = ""
            if self.state_history:
                last_state = self.state_history[-1]
                regression_info = f"""
**Regression Detection**:
- Previous URL: {last_state.get('url', 'unknown')}
- Previous State Type: {last_state.get('state_type', 'unknown')}
- URL Changed: {last_state.get('url') != current_url}
- Check for unexpected state reversions or navigation loops
"""
            
            task = Task(
                description=f"""
You are an ADVANCED UI state validator performing CONTEXT-AWARE validation. Your goal is to:
1. Validate the current UI state comprehensively
2. Detect SILENT FAILURES (actions that appear to succeed but don't complete)
3. Identify state REGRESSIONS (unexpected state changes or reversions)
4. Verify state TRANSITIONS are complete (not stuck in intermediate states)

{context_info}

{regression_info}

**CRITICAL: CONTEXT-AWARE VALIDATION** (not just DOM checking):

1. **Silent Failure Detection**:
   - Did the previous action ACTUALLY complete? (check page text, URL, forms, modals)
   - If action was "click button", did it trigger expected state change?
   - If action was "type text", is the text visible in forms or confirmation?
   - Look for subtle signs of failure: error toasts, validation messages, unchanged state
   
2. **State Transition Verification**:
   - Is the state change COMPLETE or stuck halfway?
   - Are we in an intermediate loading state?
   - Did modals/popups open as expected from the action?
   - Are expected elements now visible/hidden based on the action?

3. **Regression Detection**:
   - Did we loop back to a previous state unexpectedly?
   - Did the URL change in an unexpected way?
   - Are we stuck on the same page after an action that should navigate?
   
4. **Error Detection** (comprehensive):
   - Visible error messages, alerts, warnings, toasts
   - Form validation errors (red text, error borders, validation messages)
   - Network errors (404, 500, connection failed, timeout)
   - JavaScript errors affecting functionality
   - Access denied / permission errors
   - Session expired / authentication errors

5. **DOM & Content Validation**:
   - Page fully loaded (no loading spinners, skeletons, placeholders)
   - Expected elements present and visible
   - Interactive elements (buttons, forms) enabled and accessible
   - No blocking overlays (unless expected)
   - Content matches expected state

6. **Workflow Continuity**:
   - Is the current state consistent with the workflow progression?
   - Can the next step in the workflow proceed safely?
   - Are there any blockers preventing forward progress?

**Page HTML Sample** (for detailed inspection):
{page_html[:2000]}

**IMPORTANT**: 
- Be SPECIFIC about issues found (quote error messages, describe what's wrong)
- Distinguish between HARD errors (must stop) vs SOFT warnings (can continue)
- If previous action appears to have silently failed, mark as NOT valid

Return validation result as JSON with:
{{
  "valid": boolean,  // true ONLY if state is fully valid and action succeeded
  "issues": [list of specific issues found],
  "ready_to_proceed": boolean,  // true if safe to continue to next step
  "state_type": string,  // "url_state", "modal_state", "form_state", "loading_state", "error_state"
  "silent_failure_detected": boolean,  // true if action appeared to succeed but didn't
  "regression_detected": boolean,  // true if state regressed unexpectedly
  "confidence": float  // 0.0-1.0, how confident in this validation
}}
                """,
                expected_output="A comprehensive JSON validation result with valid, issues, ready_to_proceed, state_type, silent_failure_detected, regression_detected, and confidence fields.",
                agent=self.agent
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = crew.kickoff()
            
            validation_result = self._parse_validation(str(result))
            
            # Add to state history
            self.state_history.append({
                'url': current_url,
                'state_type': workflow_state.get('state_type'),
                'validation_result': validation_result,
                'timestamp': time.time(),
                'modals': len(modals),
                'forms': len(forms)
            })
            
            # Keep only last 20 states
            if len(self.state_history) > 20:
                self.state_history = self.state_history[-20:]
            
            logger.log_agent_end("StateValidatorAgent", success=validation_result.get('valid', False))
            
            # Log important findings
            if validation_result.get('silent_failure_detected'):
                logger.warning("⚠️ SILENT FAILURE DETECTED by State Validator")
            if validation_result.get('regression_detected'):
                logger.warning("⚠️ STATE REGRESSION DETECTED by State Validator")
            
            return validation_result
            
        except Exception as e:
            logger.log_error(e, context={"agent": "StateValidatorAgent"})
            logger.log_agent_end("StateValidatorAgent", success=False)
            return {
                "valid": False, 
                "issues": [str(e)], 
                "ready_to_proceed": False,
                "state_type": "error_state",
                "silent_failure_detected": False,
                "regression_detected": False,
                "confidence": 0.0
            }
    
    def _parse_validation(self, validation_text: str) -> Dict[str, Any]:
        """Parse validation result with enhanced fields"""
        import json
        import re
        
        json_match = re.search(r'\{.*\}', validation_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                # Ensure all expected fields are present
                result.setdefault('valid', False)
                result.setdefault('issues', [])
                result.setdefault('ready_to_proceed', False)
                result.setdefault('state_type', 'unknown')
                result.setdefault('silent_failure_detected', False)
                result.setdefault('regression_detected', False)
                result.setdefault('confidence', 0.5)
                return result
            except:
                pass
        
        # Fallback parsing
        valid = 'valid' in validation_text.lower() and 'true' in validation_text.lower()
        ready = 'ready' in validation_text.lower() and 'proceed' in validation_text.lower()
        
        return {
            "valid": valid,
            "issues": [] if valid else ["Validation unclear"],
            "ready_to_proceed": ready,
            "state_type": "unknown",
            "silent_failure_detected": False,
            "regression_detected": False,
            "confidence": 0.3
        }
    
    def reset_state(self):
        """Reset state history (useful between workflows)"""
        self.state_history = []
        self.validation_count = 0
        logger.info("State validator reset")
