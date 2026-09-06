"""Agent lifecycle and execution state representation."""

from enum import Enum
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentLifecycleState(str, Enum):
    """Lifecycle states of an agent execution."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    MAX_ITERATIONS = "max_iterations"


class AgentState(BaseModel):
    """Encapsulates runtime state of a single agent execution."""

    run_id: str
    session_id: str
    lifecycle: AgentLifecycleState = AgentLifecycleState.CREATED
    iteration: int = 0
    tool_call_count: int = 0
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Calculates elapsed execution time in seconds."""
        end = self.end_time or time.time()
        return max(0.0, end - self.start_time)

    def transition(self, new_state: AgentLifecycleState, error: Optional[str] = None) -> None:
        """Transitions to a new lifecycle state."""
        self.lifecycle = new_state
        if error:
            self.error = error
        if new_state in {
            AgentLifecycleState.COMPLETED,
            AgentLifecycleState.FAILED,
            AgentLifecycleState.CANCELLED,
            AgentLifecycleState.TIMEOUT,
            AgentLifecycleState.MAX_ITERATIONS,
        }:
            self.end_time = time.time()
