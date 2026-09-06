"""Agent execution result models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..models.base import ModelUsage


class ToolCallRecord(BaseModel):
    """Audit record of a single tool execution within an agent turn."""

    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: float = 0.0
    approved: bool = True


class AgentResult(BaseModel):
    """Structured result returned from an agent execution run."""

    text: str = Field(default="", description="The final text response from the agent.")
    structured: Optional[Any] = Field(default=None, description="Parsed Pydantic response model if requested.")
    run_id: str = Field(default="", description="Unique ID for this run.")
    session_id: str = Field(default="", description="Session ID for context tracking.")
    usage: ModelUsage = Field(default_factory=ModelUsage, description="Token usage details.")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="Tool calls executed during the run.")
    iterations: int = Field(default=0, description="Number of execution loop iterations.")
    duration: float = Field(default=0.0, description="Total execution duration in seconds.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata.")

    status: str = Field(default="completed", description="Execution status e.g. completed, requires_approval, error.")
    pending_approvals: List[Dict[str, Any]] = Field(default_factory=list, description="Pending human approval requests if paused.")

    # Backward compatibility properties with AgentResponse
    @property
    def content(self) -> str:
        """Alias for text for backward compatibility with AgentResponse."""
        return self.text

    @property
    def accumulated_content(self) -> str:
        """Alias for text for backward compatibility with AgentResponse."""
        return self.text

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.metadata:
            return self.metadata[item]
        raise KeyError(item)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.metadata

    def __str__(self) -> str:
        """Convenient printing of agent result."""
        return self.text
