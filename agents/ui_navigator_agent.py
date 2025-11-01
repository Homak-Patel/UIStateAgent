from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from typing import Optional, Dict, Any, List
from utils.logger import get_logger
from utils.browser_controller import BrowserController

logger = get_logger(name="ui_navigator_agent")


class UINavigatorAgent:
    def __init__(self, browser: BrowserController, llm_model: str = "gpt-4"):
        self.browser = browser
        self.llm = self._get_llm(llm_model)
        self.agent = Agent(
            role="UI Navigation Specialist",
            goal="Navigate web applications and interact with UI elements to complete tasks",
            backstory="Expert in web UI navigation, understanding user flows, and identifying clickable elements",
            verbose=True,
            llm=self.llm
        )
    
    def _get_llm(self, model: str):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        if "claude" in model.lower() or "anthropic" in model.lower():
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            return ChatAnthropic(model=model, api_key=api_key)
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found")
            return ChatOpenAI(model=model, temperature=0.7, api_key=api_key)
    
    async def navigate_to_task(self, task_query: str, app_url: str) -> List[Dict[str, Any]]:
        logger.log_agent_start("UINavigatorAgent", task=task_query)
        
        try:
            await self.browser.navigate(app_url)
            current_url = await self.browser.get_url()
            
            task = Task(
                description=f"""
                Analyze the task: {task_query}
                Current URL: {current_url}
                
                Determine the navigation steps needed:
                1. Identify buttons/links to click
                2. Identify forms to fill
                3. Identify modals to open
                4. Provide step-by-step navigation plan
                
                Return a JSON list of actions with:
                - action_type: click, type, wait, navigate
                - selector: CSS selector or text content
                - description: what this action does
                """,
                expected_output="A JSON list of navigation actions, each containing action_type, selector, and description fields.",
                agent=self.agent
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = crew.kickoff()
            
            logger.log_agent_end("UINavigatorAgent", success=True)
            return self._parse_navigation_plan(str(result))
        except Exception as e:
            logger.log_error(e, context={"agent": "UINavigatorAgent"})
            logger.log_agent_end("UINavigatorAgent", success=False)
            raise
    
    def _parse_navigation_plan(self, plan_text: str) -> List[Dict[str, Any]]:
        import json
        import re
        
        json_match = re.search(r'\[.*\]', plan_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        steps = []
        lines = plan_text.split('\n')
        for line in lines:
            if 'click' in line.lower() or 'type' in line.lower() or 'navigate' in line.lower():
                action_type = 'click' if 'click' in line.lower() else 'type' if 'type' in line.lower() else 'navigate'
                steps.append({
                    'action_type': action_type,
                    'selector': line.strip(),
                    'description': line.strip()
                })
        
        return steps if steps else [{'action_type': 'navigate', 'description': plan_text}]
