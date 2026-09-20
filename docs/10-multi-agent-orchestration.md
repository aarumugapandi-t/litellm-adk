# Multi-Agent Orchestration & Handoffs

The LiteLLM ADK supports advanced multi-agent architectures (`src/litellm_adk/multiagent/` and `src/litellm_adk/handoff.py`), including hierarchical supervisor delegation, collective agent teams, and bidirectional control handoffs.

---

## 1. Multi-Agent Topologies

```mermaid
graph TD
    subgraph "1. Hierarchical Supervisor Pattern"
        User1["User Query"] --> Sup["Supervisor Agent"]
        Sup -->|Delegates Task| WorkerA["Research Agent"]
        Sup -->|Delegates Task| WorkerB["Coder Agent"]
        WorkerA -->|Returns Findings| Sup
        WorkerB -->|Returns Code| Sup
    end

    subgraph "2. Agent Team (Roster Pattern)"
        Team["AgentTeam"]
        Team --> Member1["Billing Agent"]
        Team --> Member2["Support Agent"]
        Team --> Member3["Shipping Agent"]
    end

    subgraph "3. Control Handoff Pattern"
        User2["User"] --> Frontline["Triage Agent"]
        Frontline -->|HandoffAgent('Escalations')| Specialist["Escalations Agent"]
        Specialist -->|Direct Dialogue| User2
    end
```

---

## 2. The Supervisor Pattern (`Supervisor`)

The `Supervisor` pattern wraps specialized worker agents into tools and equips them to a coordinator agent. The supervisor analyzes the task and dispatches subtasks to the appropriate specialist:

```python
import asyncio
from litellm_adk import Agent
from litellm_adk.multiagent import Supervisor

# 1. Define specialized worker agents
research_agent = Agent(
    name="Researcher",
    model="gpt-4o",
    system_prompt="You are an expert researcher. Search and extract verified facts.",
)

writer_agent = Agent(
    name="TechnicalWriter",
    model="gpt-4o",
    system_prompt="You are a professional technical writer. Synthesize raw research into polished articles.",
)

# 2. Instantiate supervisor with worker agents
supervisor = Supervisor(
    name="EditorialSupervisor",
    model="gpt-4o",
    agents=[research_agent, writer_agent],
    system_prompt="Coordinate research and writing. First instruct the Researcher, then pass findings to the TechnicalWriter.",
)

async def main():
    result = await supervisor.ainvoke(
        "Write an executive briefing on recent advances in quantum error correction."
    )
    print("Supervisor Result:\n", result.text)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. Agent Teams (`AgentTeam`)

An `AgentTeam` manages a roster of specialized agents that can be embedded into higher-level workflows or exposed as tools:

```python
from litellm_adk.multiagent import AgentTeam

team = AgentTeam([research_agent, writer_agent])

# Retrieve all agents wrapped as callable Tools
team_tools = team.get_tools()

orchestrator = Agent(
    name="ExecutiveDirector",
    model="gpt-4o",
    tools=team_tools,
)
```

---

## 4. Agent-as-a-Tool (`agent_as_tool`)

Any `Agent` instance can be automatically wrapped as a callable `Tool` using `agent_as_tool`:

```python
from litellm_adk.multiagent import agent_as_tool

data_analyst = Agent(
    name="DataAnalyst",
    model="gpt-4o",
    system_prompt="Executes statistical analysis on numerical data arrays.",
)

# Converts the agent into a standard Tool with OpenAPI schema
analyst_tool = agent_as_tool(data_analyst)

# Primary agent can now call data_analyst like any other function tool
lead_agent = Agent(
    name="ProjectLead",
    model="gpt-4o",
    tools=[analyst_tool],
)
```

---

## 5. Control Transfer Handoffs (`HandoffAgent`)

For conversational workflows where control transfers completely to another agent (e.g. from general triage to a tier-2 billing specialist):

```python
from litellm_adk.handoff import HandoffAgent

def transfer_to_billing(account_id: str):
    """Transfers the live conversation to the specialized billing agent."""
    raise HandoffAgent("BillingSpecialist", account_id=account_id)
```

The runtime intercepts `HandoffAgent`, swaps the active agent context to `"BillingSpecialist"`, and continues conversation without losing prior history.
