"""Streaming and Event Handling Example.

Demonstrates real-time event streaming and handling fine-grained lifecycle events.
"""

import asyncio
import os
from litellm_adk import Agent, tool


@tool
async def fetch_stock_price(symbol: str) -> str:
    """Fetches real-time stock ticker price."""
    await asyncio.sleep(0.5)  # Simulate network latency
    mock_prices = {"AAPL": "225.50 USD", "GOOGL": "180.20 USD", "MSFT": "415.00 USD"}
    return mock_prices.get(symbol.upper(), "Unknown symbol")


async def main():
    agent = Agent(
        name="finance_streamer",
        model="openrouter/mistralai/ministral-3b-2512",
        api_key="sk-1234",
        base_url="http://localhost:9000/v1",
        system_prompt="You are a financial advisor assistant. Explain what the stock prices mean and provide context.",
        tools=[fetch_stock_price],
    )

    query = "Check the current price of AAPL and explain its market standing briefly."
    print(f"Query: {query}\n--- Streaming Output ---")

    async for event in agent.stream(query):
        if event.type == "agent.started":
            print("[Event: Agent Started]")
        elif event.type == "tool.started":
            print(f"\n[Event: Tool Call Started -> {event.data.get('tool_name')}]")
        elif event.type == "tool.completed":
            print(f"[Event: Tool Call Completed -> Result: {event.data.get('result')}]\n")
        elif event.type == "text.delta":
            print(event.data.get("delta", ""), end="", flush=True)
        elif event.type == "agent.finished":
            print("\n\n[Event: Agent Finished]")

    print("\nStream finished successfully.")


if __name__ == "__main__":
    asyncio.run(main())
