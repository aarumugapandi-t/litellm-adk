"""RunStore implementations."""

from typing import Dict, Optional
from ..agent.result import AgentResult
from .base import RunStore


class InMemoryRunStore(RunStore):
    """In-memory run results store."""

    def __init__(self):
        self._runs: Dict[str, AgentResult] = {}

    async def save_run(self, result: AgentResult) -> None:
        self._runs[result.run_id] = result

    async def get_run(self, run_id: str) -> Optional[AgentResult]:
        return self._runs.get(run_id)
