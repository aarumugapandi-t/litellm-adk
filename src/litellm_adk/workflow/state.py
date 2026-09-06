"""Workflow execution state and runtime tracking models."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Runtime execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeExecutionRecord(BaseModel):
    """Execution audit trail and metrics for an individual node."""
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


class ExecutionState(BaseModel):
    """Cumulative state of a workflow execution run."""
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
