from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from typing import Optional, Dict, Any, List
from utils.logger import get_logger
from utils.upstash_sync import UpstashSync
import time
import json

logger = get_logger(name="context_sync_agent")


class ContextSyncAgent:
    def __init__(self, llm_model: str = "claude-sonnet-4-5-20250929"):
        self.llm = self._get_llm(llm_model)
        self.upstash = UpstashSync()
        self.agent = Agent(
            role="Advanced Context Synchronization & State Management Specialist",
            goal="Ensure seamless context flow and state consistency across all agents - preventing desyncs and flow breaks",
            backstory="""Expert in distributed agent coordination with deep understanding of:
            - Cross-agent state synchronization
            - Workflow continuity management
            - Context versioning and conflict resolution
            - Agent-to-agent communication patterns
            - Failure recovery and context restoration
            - Real-time state tracking across navigation, validation, and screenshot agents""",
            verbose=True,
            llm=self.llm
        )
        # Local context cache for fast access
        self.local_cache: Dict[str, Dict[str, Any]] = {}
        self.context_version = 0
        self.sync_history: List[Dict[str, Any]] = []
    
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
    
    def save_context(
        self, 
        key: str, 
        context_data: Dict[str, Any], 
        ttl: Optional[int] = None,
        critical: bool = False
    ) -> bool:
        """
        Save context with versioning and local caching
        
        Args:
            key: Context key
            context_data: Data to save
            ttl: Time-to-live in seconds
            critical: If True, raises error on failure
        """
        logger.log_agent_start("ContextSyncAgent", task=f"Save context: {key}")
        
        try:
            # Add version and timestamp
            self.context_version += 1
            enriched_data = {
                **context_data,
                "_context_version": self.context_version,
                "_timestamp": time.time(),
                "_key": key
            }
            
            # Save to local cache first (always succeeds)
            self.local_cache[key] = enriched_data
            
            # Try to sync to Upstash (optional, for distributed access)
            try:
                context_json = json.dumps(enriched_data, default=str)
                upstash_success = self.upstash.set(key, context_json, ttl=ttl)
                
                if upstash_success:
                    logger.debug(f"Context synced to Upstash: {key}")
                else:
                    logger.debug(f"Upstash sync skipped for: {key}")
            except Exception as e:
                logger.debug(f"Upstash unavailable (using local cache only): {str(e)[:100]}")
            
            # Track sync event
            self.sync_history.append({
                'key': key,
                'action': 'save',
                'version': self.context_version,
                'timestamp': time.time(),
                'size_bytes': len(context_json) if 'context_json' in locals() else 0
            })
            
            # Keep only last 50 sync events
            if len(self.sync_history) > 50:
                self.sync_history = self.sync_history[-50:]
            
            logger.log_agent_end("ContextSyncAgent", success=True)
            return True
            
        except Exception as e:
            logger.log_error(e, context={"agent": "ContextSyncAgent", "action": "save", "key": key})
            logger.log_agent_end("ContextSyncAgent", success=False)
            
            if critical:
                raise
            return False
    
    def get_context(self, key: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get context with fallback to local cache
        
        Args:
            key: Context key
            use_cache: If True, check local cache first
        """
        logger.log_agent_start("ContextSyncAgent", task=f"Get context: {key}")
        
        try:
            # Try local cache first if enabled
            if use_cache and key in self.local_cache:
                logger.debug(f"Context retrieved from local cache: {key}")
                logger.log_agent_end("ContextSyncAgent", success=True)
                return self.local_cache[key]
            
            # Try Upstash
            try:
                context_json = self.upstash.get(key)
                if context_json:
                    context_data = json.loads(context_json)
                    # Update local cache
                    self.local_cache[key] = context_data
                    logger.debug(f"Context retrieved from Upstash: {key}")
                    logger.log_agent_end("ContextSyncAgent", success=True)
                    return context_data
            except Exception as e:
                logger.debug(f"Upstash unavailable: {str(e)[:100]}")
            
            # Not found in cache or Upstash
            logger.debug(f"Context not found: {key}")
            logger.log_agent_end("ContextSyncAgent", success=False)
            return None
            
        except Exception as e:
            logger.log_error(e, context={"agent": "ContextSyncAgent", "action": "get"})
            logger.log_agent_end("ContextSyncAgent", success=False)
            return None
    
    def sync_agent_state(
        self,
        workflow_id: str,
        step: int,
        agent_name: str,
        agent_state: Dict[str, Any]
    ) -> bool:
        """
        Sync state for a specific agent at a specific workflow step
        
        This ensures all agents have access to shared state
        """
        context_key = f"{workflow_id}:step:{step}:agent:{agent_name}"
        return self.save_context(context_key, agent_state)
    
    def get_agent_state(
        self,
        workflow_id: str,
        step: int,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get state for a specific agent"""
        context_key = f"{workflow_id}:step:{step}:agent:{agent_name}"
        return self.get_context(context_key)
    
    def sync_workflow_context(
        self,
        workflow_id: str,
        step: int,
        navigation_state: Optional[Dict[str, Any]] = None,
        screenshot_state: Optional[Dict[str, Any]] = None,
        validation_state: Optional[Dict[str, Any]] = None,
        browser_state: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Sync comprehensive workflow context across all agents
        
        This maintains flow continuity by ensuring all agents have
        access to the latest state from all other agents
        """
        workflow_context = {
            'workflow_id': workflow_id,
            'step': step,
            'navigation': navigation_state or {},
            'screenshot': screenshot_state or {},
            'validation': validation_state or {},
            'browser': browser_state or {},
            'synced_at': time.time()
        }
        
        context_key = f"{workflow_id}:workflow:step:{step}"
        success = self.save_context(context_key, workflow_context, critical=True)
        
        if success:
            logger.info(f"✅ Workflow context synced for step {step}")
        
        return success
    
    def get_workflow_context(
        self,
        workflow_id: str,
        step: int
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive workflow context for a step"""
        context_key = f"{workflow_id}:workflow:step:{step}"
        return self.get_context(context_key)
    
    def detect_desync(
        self,
        workflow_id: str,
        current_step: int,
        agent_name: str
    ) -> Dict[str, Any]:
        """
        Detect if an agent has become desynced from workflow
        
        Returns:
            Dict with 'desynced' (bool), 'reason' (str), 'last_synced_step' (int)
        """
        # Get agent's last synced state
        agent_state = self.get_agent_state(workflow_id, current_step, agent_name)
        
        # Get workflow context
        workflow_context = self.get_workflow_context(workflow_id, current_step)
        
        if not agent_state:
            return {
                'desynced': True,
                'reason': f'Agent {agent_name} has no state for step {current_step}',
                'last_synced_step': None
            }
        
        if not workflow_context:
            return {
                'desynced': True,
                'reason': f'Workflow has no context for step {current_step}',
                'last_synced_step': None
            }
        
        # Check version alignment
        agent_version = agent_state.get('_context_version', 0)
        workflow_version = workflow_context.get('_context_version', 0)
        
        if abs(agent_version - workflow_version) > 5:
            return {
                'desynced': True,
                'reason': f'Version mismatch: agent={agent_version}, workflow={workflow_version}',
                'last_synced_step': current_step
            }
        
        # Check timestamp freshness
        agent_timestamp = agent_state.get('_timestamp', 0)
        workflow_timestamp = workflow_context.get('_timestamp', 0)
        
        if workflow_timestamp - agent_timestamp > 60:  # More than 60 seconds old
            return {
                'desynced': True,
                'reason': f'Stale state: agent timestamp is {workflow_timestamp - agent_timestamp:.1f}s behind',
                'last_synced_step': current_step
            }
        
        return {
            'desynced': False,
            'reason': 'Agent is in sync',
            'last_synced_step': current_step
        }
    
    def clear_workflow_context(self, workflow_id: str):
        """Clear all context for a workflow"""
        # Clear from local cache
        keys_to_remove = [k for k in self.local_cache.keys() if k.startswith(workflow_id)]
        for key in keys_to_remove:
            del self.local_cache[key]
        
        logger.info(f"Cleared workflow context for {workflow_id}")
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            'context_version': self.context_version,
            'cached_contexts': len(self.local_cache),
            'sync_events': len(self.sync_history),
            'recent_syncs': self.sync_history[-10:] if self.sync_history else []
        }
