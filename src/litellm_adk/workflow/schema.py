"""Workflow schema definitions for visual AI graph workflows."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(str, Enum):
    """Lifecycle status of a workflow."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class NodePosition(BaseModel):
    """2D coordinate position for canvas rendering."""
    x: float = 0.0
    y: float = 0.0


class WorkflowNode(BaseModel):
    """Specification of a discrete node in the workflow graph."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    name: str = ""
    version: str = "1"
    position: NodePosition = Field(default_factory=NodePosition)
    config: Dict[str, Any] = Field(default_factory=dict)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)


class WorkflowEdge(BaseModel):
    """Directed connection between two workflow nodes."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str
    target: str
    source_handle: Optional[str] = Field(None, alias="sourceHandle")
    target_handle: Optional[str] = Field(None, alias="targetHandle")


class WorkflowSettings(BaseModel):
    """Execution parameters and guardrails for a workflow."""
    timeout: int = 300
    max_concurrency: int = 10
    retry_policy: Dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    """Complete specification of an executable DAG workflow."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str = ""
    version: str = "1"
    active: bool = False
    status: WorkflowStatus = WorkflowStatus.DRAFT
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
