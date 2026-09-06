"""Multi-Tier Memory Example.

Demonstrates working memory (run state), conversation memory (multi-turn),
and long-term memory (persistent facts and preferences across sessions).
"""

import asyncio
import os
from litellm_adk import Agent, LongTermMemory


async def main():
    # 1. Initialize long-term memory with persistent user preferences
    long_term = LongTermMemory()
    await long_term.add_fact("user_name", "Sarah Connor")
    await long_term.add_fact("tone_preference", "Strictly professional, extremely concise bullet points")
    await long_term.add_fact("favorite_language", "Rust")

    # 2. Instantiate Agent
    agent = Agent(
        name="memory_assistant",
        model=os.getenv("LITELLM_MODEL", "openai/gpt-4o"),
        system_prompt="You are a personal technical assistant.",
    )
    # Inject long-term memory
    agent.long_term_memory = long_term

    # 3. Create a stateful conversation session
    session = agent.create_session(user_id="user_123")

    print("--- Turn 1: Utilizing Long-Term Memory ---")
    res1 = await agent.run("Hello! Can you recommend a programming language for a high-performance system?", session=session)
    print(f"Agent:\n{res1.text}\n")

    print("--- Turn 2: Conversation Memory Context ---")
    res2 = await agent.run("Why did you recommend that over C++?", session=session)
    print(f"Agent:\n{res2.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
