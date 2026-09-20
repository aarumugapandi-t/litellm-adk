# Getting Started with LiteLLM ADK

Welcome to the **LiteLLM Agent Development Kit (ADK)**. This guide walks you through setting up your environment, initializing your first agent, and understanding how state and tool execution work natively.

For comprehensive deep dives into every framework component, refer to the [**Documentation Index**](./README.md).

---

## 1. Prerequisites

The ADK requires Python 3.9+ and an API key for your desired Large Language Model provider.

```bash
pip install litellm-adk
```

---

## 2. Environment Configuration

Instead of hardcoding API keys and endpoints into your application, the ADK automatically reads from your environment variables. Create a `.env` file in the root of your project:

```env
# Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional Proxy / Local Model Base URL
# LITELLM_API_BASE=http://localhost:9000/v1

# Default Model Selection
LITELLM_DEFAULT_MODEL=gpt-4o
ADK_LOG_LEVEL=INFO
```

---

## 3. Your First Agent

The `Agent` class is the core orchestrator. It automatically manages conversational context, multi-turn reasoning, and tool execution.

```python
import asyncio
from litellm_adk import Agent, tool

# 1. Define a tool with automatic schema inference
@tool(description="Calculates simple interest on an investment.")
def calculate_interest(principal: float, rate_pct: float, time_years: float) -> dict:
    interest = (principal * rate_pct * time_years) / 100.0
    return {
        "principal": principal,
        "interest": round(interest, 2),
        "total": round(principal + interest, 2),
    }

async def main():
    # 2. Instantiate the agent
    agent = Agent(
        name="FinanceAssistant",
        model="gpt-4o",
        system_prompt="You are a helpful financial assistant. Use your tools for precise computations.",
        tools=[calculate_interest],
    )

    # 3. Asynchronously invoke the agent
    response = await agent.ainvoke(
        "If I invest $5,000 at 6% annual rate for 3 years, what is the interest and total?"
    )
    print("Agent Response:\n", response.text)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Visual Workflow Canvas & Prompt-to-Agent Studio

The ADK includes a full visual canvas and autonomous agent synthesizer.

To launch the web studio:
```bash
python -m litellm_adk.server
```
Visit `http://localhost:8000` to interact with:
- The **"✨ Prompt to Agent"** modal to synthesize agents and tools from natural language.
- Drag-and-drop workflow canvas with live WebSocket execution monitoring.

---

## 5. Next Steps

- Explore the complete [Architecture Overview](./01-architecture-overview.md).
- Learn about the [Agent Framework & Core Reasoning Loop](./03-agent-framework.md).
- Discover how to build [Dynamic Tools & Safe Sandboxes](./04-tools-and-dynamic-tooling.md).
- Read the [Workflow Orchestration Engine Guide](./06-workflow-orchestration-engine.md).
