"""Workflow execution state and runtime tracking models."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ExecutionStatus(str, Enum):
    """Runtime execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def safe_serialize(val: Any) -> Any:
    """Recursively converts non-serializable objects (like Tools or Callables) into JSON-friendly structures."""
    if val is None or isinstance(val, (str, int, float, bool)):
        return val
    if hasattr(val, "to_dict") and callable(getattr(val, "to_dict")):
        try:
            return val.to_dict()
        except Exception:
            pass
    if hasattr(val, "name") and hasattr(val, "func") and hasattr(val, "permissions"):
        return {
            "type": "tool",
            "name": getattr(val, "name", "tool"),
            "description": getattr(val, "description", ""),
        }
    if isinstance(val, dict):
        return {str(k): safe_serialize(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [safe_serialize(x) for x in val]
    if hasattr(val, "model_dump"):
        try:
            return val.model_dump(mode="json")
        except Exception:
            pass
    if callable(val):
        return f"<callable {getattr(val, '__name__', str(val))}>"
    try:
        import json
        json.dumps(val)
        return val
    except Exception:
        return str(val)


class NodeExecutionRecord(BaseModel):
    """Execution audit trail and metrics for an individual node."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    node_id: str
    node_type: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    input_data: Any = None
    output_data: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer("input_data", "output_data", "metadata", mode="plain")
    def serialize_data(self, val: Any) -> Any:
        return safe_serialize(val)


class ExecutionState(BaseModel):
    """Cumulative state of a workflow execution run."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_id: str
    workflow_id: str
    workflow_version: str = "1"
    status: ExecutionStatus = ExecutionStatus.PENDING
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    current_nodes: List[str] = Field(default_factory=list)
    completed_nodes: List[str] = Field(default_factory=list)
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    node_records: Dict[str, NodeExecutionRecord] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    pending_approval: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_duration: float = 0.0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer("trigger_data", "node_outputs", "variables", "metadata", mode="plain")
    def serialize_state_data(self, val: Any) -> Any:
        return safe_serialize(val)
