"""Working memory (Deprecated).

WorkingMemory has been deprecated and decoupled from AgentLoop in favor of the native
LLM message scratchpad ([user, assistant (tool_calls), tool (result), assistant]).
This class is retained purely for backward-compatibility with external callers.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkingMemory(BaseModel):
    """(Deprecated) Legacy scratchpad for ongoing agent execution turns."""

    current_task: Optional[str] = None
    plan: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    tool_results: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    retrieved_documents: List[str] = Field(default_factory=list, description="Ephemeral RAG context for the active turn.")

    def set_task(self, task: str) -> None:
        self.current_task = task

    def set_plan(self, steps: List[str]) -> None:
        self.plan = steps

    def add_observation(self, observation: str) -> None:
        self.observations.append(observation)

    def record_tool_result(self, tool_name: str, result_or_args: Any, result: Optional[Any] = None) -> None:
        if result is not None:
            self.tool_results[tool_name] = {"arguments": result_or_args, "result": result}
            self.add_observation(f"Tool '{tool_name}' result: {result}")
        else:
            self.tool_results[tool_name] = result_or_args
            self.add_observation(f"Tool '{tool_name}' result: {result_or_args}")

    def set_variable(self, key: str, value: Any) -> None:
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set_retrieved_documents(self, documents: List[str]) -> None:
        """Stores ephemeral RAG retrieved document chunks for the active turn."""
        self.retrieved_documents = list(documents)

    def get_retrieved_documents(self) -> List[str]:
        """Returns the ephemeral RAG documents for the active turn."""
        return list(self.retrieved_documents)

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
        self.retrieved_documents.clear()
