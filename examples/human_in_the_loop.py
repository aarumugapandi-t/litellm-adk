"""Human-in-the-Loop (HITL) Example.

Demonstrates intercepting sensitive tool actions with human approval gating
using programmatic CallbackHumanLoop and interactive ConsoleHumanLoop.
"""

import asyncio
import os
from typing import Any, Dict
from litellm_adk import Agent, CallbackHumanLoop, ToolPermission, tool


# 1. Define sensitive tool requiring approval
@tool(
    name="transfer_funds",
    description="Transfers money from the user account to a destination account.",
    permissions={ToolPermission.DANGEROUS},
    requires_approval=True,  # Safety flag triggering HITL
)
async def transfer_funds(to_account: str, amount: float) -> str:
    """Simulates financial fund transfer."""
    return f"Successfully transferred ${amount:.2f} to account {to_account}."


async def main():
    # 2. Define human approval handler (can be connected to a UI, Slack, or webhook)
    async def approval_handler(tool_name: str, tool_call_id: str, args: Dict[str, Any]):
        print(f"\n[HITL Guardrail] Approval requested for '{tool_name}'")
        print(f"Details: Send ${args.get('amount')} to {args.get('to_account')}")

        # In an automated demo or test, simulate human decision:
        if args.get("amount", 0) > 1000:
            print("[Human Decision] REJECTED: Amount exceeds single transaction limit.")
            return False  # Rejects tool execution
        else:
            print("[Human Decision] APPROVED by compliance manager.")
            return args  # Approves tool execution

    hitl = CallbackHumanLoop(approval_callback=approval_handler)

    agent = Agent(
        name="banking_bot",
        model="openrouter/mistralai/ministral-3b-2512",
        api_key="sk-1234",
        base_url="http://localhost:9000/v1",
        system_prompt="You are a personal banking assistant. Execute transfers requested by the user and explain the process clearly.",
        tools=[transfer_funds],
        human_in_the_loop=hitl,
    )

    print("--- Scenario 1: Approved Transfer ($250) ---")
    res1 = await agent.ainvoke("Please transfer $250 to account US-99124.")
    print(f"Agent:\n{res1.text}\n")

    print("--- Scenario 2: Rejected Transfer ($5000) ---")
    try:
        res2 = await agent.ainvoke("Please transfer $5000 to account US-99124.")
        print(f"Agent:\n{res2.text}\n")
    except Exception as e:
        print(f"Execution halted as expected: {e}")


if __name__ == "__main__":
    asyncio.run(main())
