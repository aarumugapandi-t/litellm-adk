"""Basic Agent Example.

Demonstrates creating and running the simplest possible agent using Agent.run().
"""

import asyncio
import os
from litellm_adk import Agent, tool

@tool
def greet_user(name: str) -> str:
    """Simple tool to greet a user by name."""
    return f"Hello, {name}! Welcome to LiteLLM ADK."

async def main():
    # 1. Instantiate the agent
    agent = Agent(
        name="assistant",
        model=os.getenv("LITELLM_MODEL", "openai/command-a-03-2025"),
        api_key=os.getenv("LITELLM_API_KEY", "sk-1234"),
        base_url=os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
        tools=[greet_user],
        system_prompt="Your a greeter."
    )

    # 2. Run the agent asynchronously using ainvoke (or synchronously using agent.invoke)
    result = await agent.ainvoke("I'm pandi.")

    # 3. Print the structured result
    print(f"\nResponse:\n{result.text}")
    print(f"\nExecution stats: {result.duration:.2f}s, {result.usage.total_tokens} tokens")


if __name__ == "__main__":
    asyncio.run(main())
