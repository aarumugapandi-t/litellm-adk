"""Working memory representing temporary state during an agent run."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkingMemory(BaseModel):
    """Temporary scratchpad for an ongoing agent execution turn/session."""

    current_task: Optional[str] = None
    plan: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    tool_results: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)

    def set_task(self, task: str) -> None:
        self.current_task = task

    def set_plan(self, steps: List[str]) -> None:
        self.plan = steps

    def add_observation(self, observation: str) -> None:
        self.observations.append(observation)

    def record_tool_result(self, tool_name: str, result: Any) -> None:
        self.tool_results[tool_name] = result

    def set_variable(self, key: str, value: Any) -> None:
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def get_summary_notes(self) -> List[str]:
        """Returns working memory notes suitable for model context injection."""
        notes = []
        if self.current_task:
            notes.append(f"Current Task: {self.current_task}")
        if self.plan:
            notes.append("Current Plan: " + " -> ".join(self.plan))
        for obs in self.observations[-5:]:
            notes.append(f"Observation: {obs}")
        return notes

    def clear(self) -> None:
        self.current_task = None
        self.plan.clear()
        self.observations.clear()
        self.tool_results.clear()
        self.variables.clear()
