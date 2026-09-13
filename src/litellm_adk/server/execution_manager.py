"""In-memory active execution tracker and manager."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ..workflow.engine import WorkflowEngine
from ..workflow.state import ExecutionState, ExecutionStatus
from ..persistence.sqlite_workflow import execution_repository
from .routes.stream import stream_manager


class ExecutionManager:
    """Tracks active running engines to support live state queries and immediate cancellation."""

    def __init__(self):
        self._active: Dict[str, Tuple[WorkflowEngine, ExecutionState, Optional[asyncio.Task]]] = {}

    def register(
        self,
        exec_id: str,
        engine: WorkflowEngine,
        state: ExecutionState,
        task: Optional[asyncio.Task] = None
    ) -> None:
        self._active[exec_id] = (engine, state, task)

    def get_live_state(self, exec_id: str) -> Optional[ExecutionState]:
        if exec_id in self._active:
            return self._active[exec_id][1]
        return None

    def unregister(self, exec_id: str) -> None:
        self._active.pop(exec_id, None)

    async def cancel(self, exec_id: str) -> Optional[ExecutionState]:
        """Cancels an active execution in memory or marks it cancelled in persistent storage."""
        if exec_id in self._active:
            engine, state, task = self._active[exec_id]
            engine.cancel()
            if task and not task.done():
                task.cancel()
            state.status = ExecutionStatus.CANCELLED
            state.finished_at = datetime.now(timezone.utc).isoformat()
            await execution_repository.save(state)
            await stream_manager.broadcast(exec_id, {
                "type": "workflow.cancelled",
                "execution_id": exec_id,
            })
            self.unregister(exec_id)
            return state

        # If not active in memory, check persistent storage
        state = await execution_repository.get(exec_id)
        if state and state.status in (
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.WAITING_FOR_HUMAN
        ):
            state.status = ExecutionStatus.CANCELLED
            state.finished_at = datetime.now(timezone.utc).isoformat()
            await execution_repository.save(state)
            await stream_manager.broadcast(exec_id, {
                "type": "workflow.cancelled",
                "execution_id": exec_id,
            })
            return state
        return state


active_execution_manager = ExecutionManager()
