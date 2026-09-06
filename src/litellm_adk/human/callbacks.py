"""Callback-based Human-in-the-Loop adapter."""

import inspect
from typing import Any, Callable, Dict, Optional, Tuple, Union

from ..exceptions import HumanInterventionError
from .base import ApprovalDecision, HumanInTheLoop


class CallbackHumanLoop(HumanInTheLoop):
    """Executes custom async or sync callback handlers when approval or input is needed."""

    def __init__(
        self,
        approval_callback: Optional[Callable[..., Any]] = None,
        input_callback: Optional[Callable[[str], Any]] = None,
    ):
        self.approval_callback = approval_callback
        self.input_callback = input_callback

    async def request_approval(
        self,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.approval_callback:
            # Default to approved if no approval callback was provided
            return arguments

        if inspect.iscoroutinefunction(self.approval_callback):
            decision = await self.approval_callback(tool_name, tool_call_id, arguments)
        else:
            decision = self.approval_callback(tool_name, tool_call_id, arguments)

        # Decision can be bool (True=approved, False=rejected), dict (modified args), or tuple (decision, mod_args)
        if isinstance(decision, bool):
            if decision:
                return arguments
            raise HumanInterventionError(f"Tool call '{tool_name}' rejected via callback.", request_id=tool_call_id)

        if isinstance(decision, dict):
            return decision

        if isinstance(decision, tuple) and len(decision) == 2:
            status, mod_args = decision
            if status in (ApprovalDecision.APPROVE, "approved", True):
                return mod_args if mod_args is not None else arguments
            raise HumanInterventionError(f"Tool call '{tool_name}' rejected via callback.", request_id=tool_call_id)

        return arguments

    async def request_input(self, prompt: str) -> str:
        if not self.input_callback:
            return ""

        if inspect.iscoroutinefunction(self.input_callback):
            return str(await self.input_callback(prompt))
        return str(self.input_callback(prompt))
