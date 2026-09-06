"""Terminal-based Human-in-the-Loop interaction."""

import asyncio
import json
from typing import Any, Dict, Optional

from ..exceptions import HumanInterventionError
from .base import HumanInTheLoop


class ConsoleHumanLoop(HumanInTheLoop):
    """Interactive console prompt for tool approvals and user input."""

    async def request_approval(
        self,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()

        def _prompt() -> Dict[str, Any]:
            print("\n" + "=" * 50)
            print("⚠️  HUMAN APPROVAL REQUIRED")
            print(f"Tool: {tool_name} (ID: {tool_call_id})")
            if description:
                print(f"Description: {description}")
            print(f"Arguments:\n{json.dumps(arguments, indent=2)}")
            print("=" * 50)

            choice = input("Approve tool execution? ([y]es / [n]o / [m]odify args): ").strip().lower()

            if choice in ("y", "yes"):
                print("✅ Tool call approved.")
                return arguments
            elif choice in ("m", "modify"):
                mod_str = input("Enter modified arguments as JSON: ").strip()
                try:
                    mod_args = json.loads(mod_str)
                    print("✏️ Tool arguments modified and approved.")
                    return mod_args
                except Exception as e:
                    print(f"Failed to parse JSON ({e}). Reverting to rejection.")
                    raise HumanInterventionError(f"Rejected due to invalid modified arguments: {e}")
            else:
                reason = input("Provide rejection reason (optional): ").strip() or "User rejected execution in console."
                print(f"❌ Tool call rejected: {reason}")
                raise HumanInterventionError(f"Tool execution rejected by human: {reason}", request_id=tool_call_id, reason=reason)

        return await loop.run_in_executor(None, _prompt)

    async def request_input(self, prompt: str) -> str:
        loop = asyncio.get_running_loop()

        def _input() -> str:
            print(f"\n❓ Agent requests input:\n{prompt}")
            return input("> ").strip()

        return await loop.run_in_executor(None, _input)
