from typing import Any, Dict, Optional

class HandoffAgent(Exception):
    """Exception-like object to trigger control handoff to a sub-agent."""
    def __init__(self, target_agent_name: str, **kwargs):
        super().__init__(f"Handoff to {target_agent_name}")
        self.target_agent_name = target_agent_name
        self.kwargs = kwargs

class HandoffResult:
    """The result of a completed handoff execution."""
    def __init__(self, content: Any, state_updates: Optional[Dict[str, Any]] = None):
        self.content = content
        self.state_updates = state_updates or {}
