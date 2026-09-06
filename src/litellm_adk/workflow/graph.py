"""DAG graph analysis, cycle detection, and topological scheduling."""

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple
from .schema import WorkflowDefinition, WorkflowNode, WorkflowEdge
from ..exceptions import AgentError


class WorkflowGraphError(AgentError):
    """Raised when a workflow graph violates DAG constraints or has invalid connections."""
    pass


class WorkflowGraph:
    """Manages graph structure, validation, and dependency scheduling."""

    def __init__(self, definition: WorkflowDefinition):
        self.definition = definition
        self.nodes_by_id: Dict[str, WorkflowNode] = {n.id: n for n in definition.nodes}
        self.edges_by_source: Dict[str, List[WorkflowEdge]] = defaultdict(list)
        self.edges_by_target: Dict[str, List[WorkflowEdge]] = defaultdict(list)
        self.in_degree: Dict[str, int] = {n.id: 0 for n in definition.nodes}

        for edge in definition.edges:
            self.edges_by_source[edge.source].append(edge)
            self.edges_by_target[edge.target].append(edge)
            if edge.target in self.in_degree:
                self.in_degree[edge.target] += 1

    def validate(self) -> None:
        """Validates graph connectivity and verifies absence of directed cycles."""
        # Check node uniqueness
        seen_ids = set()
        for node in self.definition.nodes:
            if node.id in seen_ids:
                raise WorkflowGraphError(f"Duplicate node ID detected: {node.id}")
            seen_ids.add(node.id)

        # Check edge endpoints
        for edge in self.definition.edges:
            if edge.source not in self.nodes_by_id:
                raise WorkflowGraphError(f"Edge references non-existent source node '{edge.source}'")
            if edge.target not in self.nodes_by_id:
                raise WorkflowGraphError(f"Edge references non-existent target node '{edge.target}'")

        # Cycle detection using Kahn's algorithm
        in_deg = dict(self.in_degree)
        queue = deque([n_id for n_id, deg in in_deg.items() if deg == 0])
        visited_count = 0

        while queue:
            node_id = queue.popleft()
            visited_count += 1
            for edge in self.edges_by_source.get(node_id, []):
                in_deg[edge.target] -= 1
                if in_deg[edge.target] == 0:
                    queue.append(edge.target)

        if visited_count < len(self.nodes_by_id):
            raise WorkflowGraphError("Cycle detected in workflow graph; workflows must be directed acyclic graphs (DAGs).")

    def get_trigger_nodes(self) -> List[WorkflowNode]:
        """Returns root entry nodes (in-degree 0 or trigger type)."""
        triggers = []
        for n in self.definition.nodes:
            if "trigger" in n.type.lower() or self.in_degree[n.id] == 0:
                triggers.append(n)
        return triggers

    def get_dependencies(self, node_id: str) -> List[str]:
        """Returns list of upstream node IDs that feed directly into node_id."""
        return [edge.source for edge in self.edges_by_target.get(node_id, [])]

    def get_outgoing_edges(self, node_id: str, handle: str = None) -> List[WorkflowEdge]:
        """Returns outgoing edges from node_id, optionally filtered by source handle."""
        edges = self.edges_by_source.get(node_id, [])
        if handle is not None:
            return [e for e in edges if e.source_handle is None or e.source_handle == handle]
        return edges

    def get_topological_batches(self) -> List[List[WorkflowNode]]:
        """Groups nodes into sequential execution levels for concurrent batching."""
        in_deg = dict(self.in_degree)
        current_level = [n_id for n_id, deg in in_deg.items() if deg == 0]
        levels = []

        while current_level:
            levels.append([self.nodes_by_id[nid] for nid in current_level])
            next_level = []
            for nid in current_level:
                for edge in self.edges_by_source.get(nid, []):
                    in_deg[edge.target] -= 1
                    if in_deg[edge.target] == 0:
                        next_level.append(edge.target)
            current_level = next_level

        return levels
