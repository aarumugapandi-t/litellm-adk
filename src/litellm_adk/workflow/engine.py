"""Asynchronous DAG Workflow Engine orchestrating multi-node execution."""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone

from .schema import WorkflowDefinition, WorkflowNode, WorkflowEdge
from .graph import WorkflowGraph
from .state import ExecutionState, ExecutionStatus, NodeExecutionRecord
from .nodes.base import NodeContext, NodeResult
from .nodes.registry import node_registry, NodeRegistry
from ..events.bus import EventBus
from ..observability.logger import adk_logger


class WorkflowEngine:
    """Orchestrates validation, scheduling, and asynchronous execution of visual DAG workflows."""

    def __init__(
        self,
        registry: Optional[NodeRegistry] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.registry = registry or node_registry
        self.event_bus = event_bus or EventBus()
        self._event_subscribers: List[Callable[[str, Dict[str, Any]], Any]] = []
        self._cancelled: bool = False
        self._active_tasks: Set[asyncio.Task] = set()

    def cancel(self) -> None:
        """Cancels the currently running execution."""
        self._cancelled = True
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()

    def subscribe(self, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        """Subscribes an async or sync callback to receive live workflow events."""
        self._event_subscribers.append(callback)

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Dispatches an event to the local event bus and any subscribed listeners."""
        payload = {"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), **data}
        for sub in self._event_subscribers:
            try:
                res = sub(event_type, payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                adk_logger.warning(f"Error in workflow event subscriber: {e}")

    async def execute(
        self,
        workflow: WorkflowDefinition,
        trigger_data: Optional[Dict[str, Any]] = None,
        existing_state: Optional[ExecutionState] = None,
        human_decision: Optional[Dict[str, Any]] = None,
    ) -> ExecutionState:
        """
        Executes a workflow DAG to completion or until paused for human approval.
        """
        graph = WorkflowGraph(workflow)
        graph.validate()

        now_str = datetime.now(timezone.utc).isoformat()
        exec_id = existing_state.execution_id if existing_state else f"exec_{uuid.uuid4().hex[:12]}"

        state = existing_state or ExecutionState(
            execution_id=exec_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            status=ExecutionStatus.RUNNING,
            trigger_data=trigger_data or {},
            variables=dict(workflow.variables),
            started_at=now_str,
        )
        state.status = ExecutionStatus.RUNNING

        await self._emit_event("workflow.started", {
            "execution_id": exec_id,
            "workflow_id": workflow.id,
            "variables": state.variables,
        })

        start_time = time.perf_counter()

        # Track active handle paths (e.g. conditional branches)
        inactive_nodes: set = set()
        active_edges_by_source: Dict[str, List[WorkflowEdge]] = dict(graph.edges_by_source)

        # Build dynamic execution queue
        # A node is ready to run when all of its active upstream dependencies have completed
        def is_node_ready(node_id: str) -> bool:
            if node_id in state.completed_nodes or node_id in inactive_nodes:
                return False
            upstream_edges = graph.edges_by_target.get(node_id, [])
            for edge in upstream_edges:
                if edge.source in inactive_nodes:
                    continue  # Inactive branches don't block
                if edge.source not in state.completed_nodes:
                    return False
            return True

        # Loop until all reachable nodes have executed or execution is paused/failed/cancelled
        while True:
            if self._cancelled:
                state.status = ExecutionStatus.CANCELLED
                break

            # Find all nodes whose dependencies are satisfied
            ready_nodes = [
                n for n in workflow.nodes
                if is_node_ready(n.id) and n.id not in state.current_nodes
            ]

            if not ready_nodes:
                # No more nodes ready to execute
                break

            # Execute ready nodes concurrently
            async def run_single_node(wnode: WorkflowNode) -> Optional[NodeResult]:
                state.current_nodes.append(wnode.id)
                n_start = time.perf_counter()
                rec_id = f"nrec_{uuid.uuid4().hex[:8]}"

                rec = NodeExecutionRecord(
                    id=rec_id,
                    node_id=wnode.id,
                    node_type=wnode.type,
                    status=ExecutionStatus.RUNNING,
                    started_at=datetime.now(timezone.utc).isoformat(),
                )
                state.node_records[wnode.id] = rec

                await self._emit_event("node.started", {
                    "execution_id": exec_id,
                    "node_id": wnode.id,
                    "node_type": wnode.type,
                    "node_name": wnode.name,
                })

                # Aggregate inputs from all completed upstream nodes
                node_inputs: Dict[str, Any] = {}
                attached_tools = []
                for edge in graph.edges_by_target.get(wnode.id, []):
                    if edge.source in state.node_outputs:
                        val = state.node_outputs[edge.source]
                        node_inputs[edge.source] = val
                        src_rec = state.node_records.get(edge.source)
                        src_type = getattr(src_rec, "node_type", "") if src_rec else ""
                        is_tool_wire = (
                            edge.target_handle == "tools"
                            or edge.source_handle == "tool"
                            or (wnode.type == "agent" and "tool" in src_type)
                        )
                        if is_tool_wire:
                            # Check metadata of source node for Tool object
                            tool_candidate = (
                                (src_rec.metadata.get("tool") if src_rec and src_rec.metadata else None)
                                or val
                            )
                            if isinstance(tool_candidate, list):
                                attached_tools.extend(tool_candidate)
                            else:
                                attached_tools.append(tool_candidate)
                        elif edge.target_handle:
                            node_inputs[edge.target_handle] = val

                if attached_tools:
                    node_inputs["tools"] = attached_tools

                # If single data input (excluding tools), also alias as 'input'
                data_inputs = [v for k, v in node_inputs.items() if k != "tools"]
                if len(data_inputs) == 1:
                    node_inputs["input"] = data_inputs[0]

                # If this is the node resuming from human decision, inject it
                if human_decision and state.pending_approval and state.pending_approval.get("node_id") == wnode.id:
                    node_inputs["__human_decision__"] = human_decision
                    state.pending_approval = None

                rec.input_data = node_inputs

                node_impl = self.registry.get_node(wnode.type)
                if not node_impl:
                    rec.status = ExecutionStatus.FAILED
                    rec.error = f"Node type '{wnode.type}' is not registered."
                    rec.finished_at = datetime.now(timezone.utc).isoformat()
                    return NodeResult(output=None, status=ExecutionStatus.FAILED, error=rec.error)

                ctx = NodeContext(
                    execution_id=exec_id,
                    workflow_id=workflow.id,
                    node_id=wnode.id,
                    node_config=wnode.config,
                    inputs=node_inputs,
                    variables=state.variables,
                    trigger_data=state.trigger_data,
                    node_outputs=dict(state.node_outputs),
                    event_bus=self.event_bus,
                )

                try:
                    result = await node_impl.execute(ctx)
                    duration = time.perf_counter() - n_start
                    rec.duration = duration
                    rec.output_data = result.output
                    rec.error = result.error
                    rec.status = result.status
                    rec.metadata = dict(result.metadata or {})
                    rec.finished_at = datetime.now(timezone.utc).isoformat()

                    if result.status == ExecutionStatus.WAITING_FOR_HUMAN:
                        await self._emit_event("human.required", {
                            "execution_id": exec_id,
                            "node_id": wnode.id,
                            "approval": result.approval_payload,
                        })
                    elif result.status == ExecutionStatus.COMPLETED:
                        await self._emit_event("node.completed", {
                            "execution_id": exec_id,
                            "node_id": wnode.id,
                            "output": result.output,
                            "duration": duration,
                        })
                    elif result.status == ExecutionStatus.CANCELLED:
                        await self._emit_event("node.failed", {
                            "execution_id": exec_id,
                            "node_id": wnode.id,
                            "error": "Node cancelled",
                        })
                    else:
                        await self._emit_event("node.failed", {
                            "execution_id": exec_id,
                            "node_id": wnode.id,
                            "error": result.error,
                        })

                    return result
                except asyncio.CancelledError:
                    duration = time.perf_counter() - n_start
                    rec.duration = duration
                    rec.status = ExecutionStatus.CANCELLED
                    rec.error = "Node execution cancelled"
                    rec.finished_at = datetime.now(timezone.utc).isoformat()
                    return NodeResult(output=None, status=ExecutionStatus.CANCELLED, error="Node execution cancelled")
                except Exception as ex:
                    duration = time.perf_counter() - n_start
                    rec.duration = duration
                    rec.status = ExecutionStatus.FAILED
                    rec.error = str(ex)
                    rec.finished_at = datetime.now(timezone.utc).isoformat()
                    await self._emit_event("node.failed", {
                        "execution_id": exec_id,
                        "node_id": wnode.id,
                        "error": str(ex),
                    })
                    return NodeResult(output=None, status=ExecutionStatus.FAILED, error=str(ex))

            # Run this batch concurrently with task cancellation tracking
            tasks = [asyncio.create_task(run_single_node(n)) for n in ready_nodes]
            for t in tasks:
                self._active_tasks.add(t)

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                for t in tasks:
                    self._active_tasks.discard(t)

            if self._cancelled:
                state.status = ExecutionStatus.CANCELLED
                break

            clean_results = []
            for r in results:
                if isinstance(r, Exception):
                    clean_results.append(NodeResult(output=None, status=ExecutionStatus.FAILED, error=str(r)))
                else:
                    clean_results.append(r)
            results = clean_results

            # Process batch outcomes
            has_pause = False
            has_failure = False

            for wnode, res in zip(ready_nodes, results):
                if wnode.id in state.current_nodes:
                    state.current_nodes.remove(wnode.id)

                if not res or res.status == ExecutionStatus.FAILED:
                    has_failure = True
                    state.errors.append(f"Node {wnode.id} failed: {res.error if res else 'Unknown error'}")
                elif res.status == ExecutionStatus.WAITING_FOR_HUMAN:
                    has_pause = True
                    state.pending_approval = res.approval_payload
                elif res.status == ExecutionStatus.CANCELLED:
                    state.status = ExecutionStatus.CANCELLED
                else:
                    state.completed_nodes.append(wnode.id)
                    state.node_outputs[wnode.id] = res.output

                    # Handle branching: if node chose a specific handle (e.g. condition node)
                    if res.selected_handle is not None:
                        for edge in graph.edges_by_source.get(wnode.id, []):
                            if edge.source_handle and edge.source_handle != res.selected_handle:
                                inactive_nodes.add(edge.target)

            if state.status == ExecutionStatus.CANCELLED or self._cancelled:
                state.status = ExecutionStatus.CANCELLED
                break

            if has_failure:
                state.status = ExecutionStatus.FAILED
                break

            if has_pause:
                state.status = ExecutionStatus.WAITING_FOR_HUMAN
                break

        total_dur = time.perf_counter() - start_time
        state.total_duration = total_dur
        state.finished_at = datetime.now(timezone.utc).isoformat()

        if state.status == ExecutionStatus.RUNNING:
            state.status = ExecutionStatus.COMPLETED
            await self._emit_event("workflow.completed", {
                "execution_id": exec_id,
                "workflow_id": workflow.id,
                "duration": total_dur,
                "outputs": state.node_outputs,
            })
        elif state.status == ExecutionStatus.FAILED:
            await self._emit_event("workflow.failed", {
                "execution_id": exec_id,
                "workflow_id": workflow.id,
                "errors": state.errors,
            })
        elif state.status == ExecutionStatus.CANCELLED:
            await self._emit_event("workflow.cancelled", {
                "execution_id": exec_id,
                "workflow_id": workflow.id,
            })

        return state
