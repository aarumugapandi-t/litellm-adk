"""Tool Calling Example.

Demonstrates first-class tool definitions, automatic OpenAPI schema generation,
permissions, and execution in the agent reasoning loop.
"""

import asyncio
import os
from litellm_adk import Agent, ToolPermission, tool


# 1. Define an async tool with metadata and permissions
@tool(
    name="get_current_weather",
    description="Get current weather for a specific city.",
    permissions={ToolPermission.READ},
    timeout=5.0,
)
async def get_current_weather(city: str, unit: str = "celsius") -> str:
    """Fetches current weather information."""
    # Simulated weather lookup
    temp = 22 if unit == "celsius" else 72
    return f"Weather in {city}: Sunny, {temp}° {unit.capitalize()}."


# 2. Define a sync computational tool
@tool(
    name="calculate",
    description="Evaluate a simple math expression.",
    permissions={ToolPermission.READ},
)
def calculate(expression: str) -> str:
    """Safely evaluates basic arithmetic expressions."""
    try:
        # Restricted safe eval for basic numbers and operators
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Unsupported characters in math expression."
        return str(eval(expression))  # noqa: S307
    except Exception as e:
        return f"Error evaluating expression: {e}"


async def main():
    agent = Agent(
        name="tool_agent",
        model="openrouter/mistralai/ministral-3b-2512",
        api_key="sk-1234",
        base_url="http://localhost:9000/v1",
        system_prompt="You are a helpful assistant with access to weather and calculator tools.",
        tools=[get_current_weather, calculate],
    )

    query = "What is the weather in Paris, and what is 45 * 12?"
    print(f"User: {query}\n")

    result = await agent.ainvoke(query)

    print(f"Agent: {result.text}\n")
    print("Executed Tool Calls:")
    for record in result.tool_calls:
        print(f"- {record.name}({record.arguments}) -> {record.result} ({record.duration:.3f}s)")


if __name__ == "__main__":
    asyncio.run(main())
