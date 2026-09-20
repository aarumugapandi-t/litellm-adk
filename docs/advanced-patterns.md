# Advanced Multi-Agent Patterns

This guide covers advanced enterprise topologies in the LiteLLM ADK, including supervisor coordination, dynamic control handoffs, and human-in-the-loop authorization.

For the complete technical references, see:
- [**10. Multi-Agent Orchestration & Handoffs**](./10-multi-agent-orchestration.md)
- [**09. Human-in-the-Loop & Approvals**](./09-human-in-the-loop-and-approvals.md)
- [**06. Workflow Orchestration Engine**](./06-workflow-orchestration-engine.md)

---

## 1. Supervisor & Worker Coordination

Wrap specialized agents as tools and equip them to a coordinator using `Supervisor`:

```python
import asyncio
from litellm_adk import Agent
from litellm_adk.multiagent import Supervisor

sql_agent = Agent(
    name="DatabaseAnalyst",
    model="gpt-4o",
    system_prompt="You write and execute SQL queries to retrieve order records.",
)

email_agent = Agent(
    name="CommunicationsAgent",
    model="gpt-4o",
    system_prompt="You draft and send customer notifications.",
)

supervisor = Supervisor(
    name="CustomerSupportLead",
    model="gpt-4o",
    agents=[sql_agent, email_agent],
    system_prompt="Coordinate customer support tasks by delegating to DatabaseAnalyst and CommunicationsAgent.",
)

async def main():
    result = await supervisor.ainvoke(
        "Look up order ORD-1029 for customer David and email him an update on shipping status."
    )
    print(result.text)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 2. Dynamic Control Handoffs (`HandoffAgent`)

For conversational systems where control transitions permanently to another agent:

```python
from litellm_adk.handoff import HandoffAgent

def transfer_to_billing(account_id: str):
    """Transfers the live conversation to the specialized billing agent."""
    raise HandoffAgent("BillingSpecialist", account_id=account_id)
```

The runtime catches `HandoffAgent`, swaps the active agent context, and resumes the dialogue seamlessly.

---

## 3. Human-in-the-Loop (HITL) Guardrails

Flag sensitive tools with `requires_approval=True` to halt the execution loop until signed off:

```python
from litellm_adk.tools import tool, ToolPermission
from litellm_adk.human import SQLiteApprovalManager

@tool(
    name="reboot_production_server",
    description="Reboots a production compute node.",
    permissions={ToolPermission.DANGEROUS},
    requires_approval=True,
)
def reboot_server(server_id: str) -> dict:
    return {"status": "rebooting", "server": server_id}

agent = Agent(
    model="gpt-4o",
    tools=[reboot_server],
    approval_manager=SQLiteApprovalManager("workflows.db"),
)
```

If the agent decides to invoke `reboot_production_server`, the execution transitions to `requires_approval` and yields back to the application or UI, awaiting an operator's approval.
