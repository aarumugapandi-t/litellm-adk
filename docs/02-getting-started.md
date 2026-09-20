# Getting Started with LiteLLM ADK

This guide walks you through installing the LiteLLM ADK, setting up your environment, creating your first autonomous agent, and launching the interactive Visual Canvas Studio.

---

## 1. Prerequisites & Installation

LiteLLM ADK requires **Python 3.9+** (Python 3.10, 3.11, 3.12, and 3.13 are fully supported).

### Install via pip
```bash
pip install litellm-adk
```

### Or clone for development
```bash
git clone https://github.com/BerriAI/litellm-adk.git
cd litellm-adk
pip install -e .
```

---

## 2. Environment Configuration

The ADK automatically reads standard provider credentials and LiteLLM configuration flags from your environment. Create a `.env` file in your project root:

```env
# Primary LLM Provider API Keys (configure whichever you plan to use)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...
GEMINI_API_KEY=AIzaSy...

# Optional: LiteLLM Proxy or Local Endpoint (Ollama, vLLM, LocalAI)
# LITELLM_API_BASE=http://localhost:9000/v1
# LITELLM_MASTER_KEY=sk-proxy-master-key

# Default Model Selection
LITELLM_DEFAULT_MODEL=gpt-4o

# Server Configuration
ADK_SERVER_HOST=0.0.0.0
ADK_SERVER_PORT=8000
ADK_LOG_LEVEL=INFO
```

---

## 3. Quickstart 1: Standalone Autonomous Agent

Here is how to create an autonomous agent with a custom Python tool using standard type annotations:

```python
import asyncio
from litellm_adk import Agent, tool

# 1. Define a tool using the @tool decorator
@tool(description="Calculates compound interest on an investment.")
def calculate_compound_interest(principal: float, rate_pct: float, years: int) -> dict:
    rate = rate_pct / 100.0
    final_amount = principal * ((1 + rate) ** years)
    interest_earned = final_amount - principal
    return {
        "principal": principal,
        "final_amount": round(final_amount, 2),
        "interest_earned": round(interest_earned, 2),
        "years": years,
    }

async def main():
    # 2. Instantiate the agent
    agent = Agent(
        name="FinancialAdvisoryAgent",
        model="gpt-4o",  # or "claude-3-5-sonnet", "ollama/llama3", etc.
        system_prompt="You are a professional financial advisor. Use your tools for precise computations.",
        tools=[calculate_compound_interest],
    )

    # 3. Invoke the agent
    response = await agent.ainvoke(
        "If I invest $10,000 at a 7.5% annual rate for 10 years, how much will I have?"
    )

    print("Agent Response:\n", response.text)
    print("\nTools Called:")
    for tc in response.tool_calls:
        print(f"- {tc.name}({tc.arguments}) -> {tc.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Quickstart 2: Launching the Visual Canvas Studio

The ADK includes a web-based Canvas Studio powered by React and React Flow for visual drag-and-drop workflow editing.

### Start the Server
```bash
python -m litellm_adk.server
```
Or use the CLI:
```bash
litellm-adk serve --port 8000 --reload
```

Open your browser at `http://localhost:8000`. You will see:
- Visual workflow canvas with drag-and-drop nodes.
- Palette for Triggers, Agents, Dynamic Tools, and Logic components.
- Top action bar with **"✨ Prompt to Agent"** studio.
- Live execution monitor with WebSocket step-by-step streaming.

---

## 5. Quickstart 3: Prompt-to-Agent Studio

1. Click **"✨ Prompt to Agent"** in the top navigation bar.
2. Enter a natural language request, for example:
   > *"Create a customer greeter agent with a personalized greeting tool"*
3. Click **"Generate Architecture"**:
   - The Master Agent parses intent, creates `GreeterAgent`, synthesizes `generate_greeting` with safe Python code, and generates the canvas wiring.
4. Click **"Apply to Canvas & Wire"**.
5. Click **"▶ Test Run"** to run the workflow and view live execution outputs!

---

## 6. Running Tests & Validation

Run the test suite using `pytest`:

```bash
# Run all unit and integration tests
pytest tests/ -v

# Run dynamic tooling & synthesis tests specifically
pytest tests/test_dynamic_tool_and_manager.py -v
```
