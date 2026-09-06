"""Base node protocols and metadata definitions."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field
from ..state import ExecutionStatus
from ...events.bus import EventBus


class NodeContext(BaseModel):
    """Execution context supplied to a node during runtime."""
    model_config = dict(arbitrary_types_allowed=True)

    execution_id: str
    workflow_id: str
    node_id: str
    node_config: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    event_bus: Optional[EventBus] = None
    approval_manager: Optional[Any] = None

    def get_eval_context(self) -> Dict[str, Any]:
        """Assembles a unified template evaluation context."""
        trigger_dict = {"input": self.trigger_data}
        if isinstance(self.trigger_data, dict):
            trigger_dict.update(self.trigger_data)

        eval_ctx: Dict[str, Any] = {
            "trigger": trigger_dict,
            "variables": dict(self.variables),
            "inputs": dict(self.inputs),
            "input": self.inputs.get("input"),
            "execution": {"id": self.execution_id},
            "session": {"id": self.execution_id},
        }

        # Add all historical and upstream node outputs
        for k, v in self.node_outputs.items():
            node_entry = {"output": v}
            if isinstance(v, dict):
                node_entry.update(v)
            eval_ctx[k] = node_entry

        # Add immediate inputs
        for k, v in self.inputs.items():
            if k not in eval_ctx:
                eval_ctx[k] = v

        return eval_ctx



class NodeResult(BaseModel):
    """Result returned by node execution."""
    output: Any = None
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    selected_handle: Optional[str] = None
    error: Optional[str] = None
    waiting_for_approval: bool = False
    approval_payload: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NodeDefinition(BaseModel):
    """Descriptor metadata and dynamic configuration schema for the visual builder."""
    type: str
    name: str
    description: str
    category: str
    icon: str
    inputs: List[str] = Field(default_factory=lambda: ["input"])
    outputs: List[str] = Field(default_factory=lambda: ["output"])
    config_schema: Dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Node(Protocol):
    """Protocol satisfied by all executable workflow nodes."""

    @property
    def definition(self) -> NodeDefinition:
        ...

    async def execute(self, context: NodeContext) -> NodeResult:
        ...
