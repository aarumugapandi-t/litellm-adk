"""Base protocols and types for Human-in-the-Loop interaction."""

from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from ..exceptions import HumanInterventionError


class ApprovalDecision(str, Enum):
    """Possible outcomes of a human approval request."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


@runtime_checkable
class HumanInTheLoop(Protocol):
    """Protocol for handling human approvals, interventions, and input requests."""

    async def request_approval(
        self,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Requests human approval for executing a sensitive tool call.

        Should return the effective arguments (modified or original) if approved,
        or raise HumanInterventionError if rejected.
        """
        ...

    async def request_input(self, prompt: str) -> str:
        """Requests additional clarification or information from a human."""
        ...
