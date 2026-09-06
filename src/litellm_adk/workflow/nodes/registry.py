"""Node Registry managing discovery and instantiation of workflow nodes."""

from typing import Dict, List, Optional, Type
from .base import Node, NodeDefinition
from .trigger import ManualTriggerNode, WebhookTriggerNode
from .llm import LLMNode
from .agent import AgentNode
from .tool import ToolNode
from .memory import MemoryNode
from .vector import VectorSearchNode
from .condition import ConditionNode
from .transform import TransformNode
from .human import HumanNode
from .output import OutputNode


class NodeRegistry:
    """Central registry of all node types supported in the visual workflow engine."""

    def __init__(self):
        self._node_classes: Dict[str, Type[Node]] = {}
        self._register_builtins()

    def _register_builtins(self):
        builtins = [
            ManualTriggerNode,
            WebhookTriggerNode,
            LLMNode,
            AgentNode,
            ToolNode,
            MemoryNode,
            VectorSearchNode,
            ConditionNode,
            TransformNode,
            HumanNode,
            OutputNode,
        ]
        for cls in builtins:
            instance = cls()
            self._node_classes[instance.definition.type] = cls

    def register(self, node_cls: Type[Node]) -> None:
        """Registers a custom node implementation."""
        instance = node_cls()
        self._node_classes[instance.definition.type] = node_cls

    def get_node(self, node_type: str) -> Optional[Node]:
        """Instantiates a node by its type identifier."""
        cls = self._node_classes.get(node_type)
        if cls:
            return cls()
        return None

    def list_definitions(self) -> List[NodeDefinition]:
        """Returns metadata definitions and JSON schemas for all registered nodes."""
        definitions = []
        for cls in self._node_classes.values():
            instance = cls()
            definitions.append(instance.definition)
        return definitions


node_registry = NodeRegistry()
