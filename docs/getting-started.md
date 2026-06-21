# Getting Started with LiteLLM ADK

Welcome to the **LiteLLM Agent Development Kit (ADK)**. This guide will walk you through setting up your environment, initializing your first agent, and understanding how state management works natively.

## 1. Prerequisites

The ADK requires Python 3.9+ and assumes you have an API key for your desired Large Language Model provider.

```bash
pip install litellm-adk
```

## 2. Environment Configuration

Instead of hardcoding API keys and endpoints into your application, the ADK automatically reads from your environment variables. Create a `.env` file in the root of your project. 

If you are using a local proxy or a custom routing layer, you can easily define a `base_url`.

```env
# Example .env file
ADK_MODEL=groq/qwen/qwen3-32b
ADK_BASE_URL=http://localhost:9000/v1
ADK_API_KEY=sk-demo-1234abcd5678efgh
ADK_LOG_LEVEL=INFO
```

## 3. Your First Agent

The `LiteLLMAgent` class is the core orchestrator. By default, it automatically manages conversational context, so you don't need to manually append user and assistant messages to a list.

```python
import asyncio
from litellm_adk import LiteLLMAgent

async def main():
    # You can configure the agent either implicitly via .env or explicitly via parameters
    agent = LiteLLMAgent(
        model="groq/qwen/qwen3-32b",
        api_key="sk-demo-1234abcd5678efgh",
        base_url="http://localhost:9000/v1",
        system_prompt="You are a helpful customer support assistant."
    )

    # The ainvoke method handles asynchronous communication with the LLM
    response = await agent.ainvoke("Hi, my name is David and my order number is 9921.")
    print(response.content)

    # Context is persisted automatically in the default memory backend
    response = await agent.ainvoke("Can you remind me what my order number is?")
    print(response.content) # Output: "Your order number is 9921."

if __name__ == "__main__":
    asyncio.run(main())
```

## 4. Next Steps

Now that you have a basic agent running, explore the framework's more powerful capabilities:
- Learn how the ADK routes requests in the Architecture Overview.
- Dive into multi-agent architectures in Advanced Patterns.
- Ensure your deployments are secure in Security & Compliance.
