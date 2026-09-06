"""Strongly typed events for the event bus and streaming interface."""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Event(BaseModel):
    """Base event structure."""

    type: str
    timestamp: float = Field(default_factory=time.time)
    run_id: str = ""
    agent_id: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        for field, val in self.__dict__.items():
            if field not in ("type", "timestamp", "run_id", "agent_id", "data") and field not in self.data:
                self.data[field] = val

    def __getitem__(self, item: str) -> Any:
        if item in self.data:
            return self.data[item]
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.data:
            return self.data[key]
        if hasattr(self, key):
            return getattr(self, key)
        return default

    def __contains__(self, item: str) -> bool:
        return item in self.data or hasattr(self, item)


class AgentStarted(Event):
    """Fired when an agent begins execution on a user prompt."""

    type: str = "agent.started"
    prompt: str = ""


class AgentFinished(Event):
    """Fired when an agent completes execution successfully."""

    type: str = "agent.finished"
    output: str = ""
    duration: float = 0.0


class AgentErrorEvent(Event):
    """Fired when an agent execution fails with an exception."""

    type: str = "agent.error"
    error: str = ""


class TextDelta(Event):
    """Fired for each streaming token/text chunk emitted by the model."""

    type: str = "text.delta"
    delta: str = ""


class ToolCallStarted(Event):
    """Fired when a tool call has been parsed and is about to execute."""

    type: str = "tool.started"
    tool_name: str = ""
    tool_call_id: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolCallCompleted(Event):
    """Fired when a tool execution completes successfully."""

    type: str = "tool.completed"
    tool_name: str = ""
    tool_call_id: str = ""
    result: Any = None
    duration: float = 0.0


class ToolCallFailed(Event):
    """Fired when a tool execution fails."""

    type: str = "tool.failed"
    tool_name: str = ""
    tool_call_id: str = ""
    error: str = ""


class HumanApprovalRequired(Event):
    """Fired when an execution requires human intervention before continuing."""

    type: str = "human.approval_required"
    tool_name: str = ""
    tool_call_id: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MemoryRetrieved(Event):
    """Fired when relevant long-term or working memories are retrieved."""

    type: str = "memory.retrieved"
    items: List[str] = Field(default_factory=list)


class MemoryCreated(Event):
    """Fired when new facts are committed to memory."""

    type: str = "memory.created"
    key: str = ""
    value: Any = None
