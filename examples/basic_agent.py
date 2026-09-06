"""Basic Agent Example.

Demonstrates creating and running the simplest possible agent using Agent.run().
"""

import asyncio
import os
from litellm_adk import Agent


async def main():
    # 1. Instantiate the agent
    agent = Agent(
        name="assistant",
        model=os.getenv("LITELLM_MODEL", "openai/gpt-4o"),
        system_prompt="You are a clear and concise programming assistant.",
    )

    # 2. Run the agent asynchronously using ainvoke (or synchronously using agent.invoke)
    print("Asking agent about recursion...")
    result = await agent.ainvoke("Explain recursion in one sentence.")

    # 3. Print the structured result
    print(f"\nResponse:\n{result.text}")
    print(f"\nExecution stats: {result.duration:.2f}s, {result.usage.total_tokens} tokens")


if __name__ == "__main__":
    asyncio.run(main())
