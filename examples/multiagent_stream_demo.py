"""
Multiagent Demo using Sub-Agents and chunk streaming
"""
import os
import asyncio
import sys
from dotenv import load_dotenv
from litellm_adk.agents import LiteLLMAgent
from litellm_adk.tools import tool

load_dotenv()

@tool
def get_user_data(user_id: str):
    """Fetch profile data for a specific user ID."""
    return f"User {user_id} is a premium member with 5 active subscriptions."

@tool
def process_refund(user_id: str, amount: float):
    """Process a refund for a user."""
    return f"Successfully refunded ${amount} to user {user_id}."

account_agent = LiteLLMAgent(
    name="account_management_agent",
    description="Handles user account queries.",
    system_prompt="You are the Account Management Specialist.",
    tools=[get_user_data],
    model="groq/qwen/qwen3-32b",
    api_key="sk-1234",
    base_url="http://localhost:9000/v1",
)

billing_agent = LiteLLMAgent(
    name="billing_agent_specialist",
    description="Handles refunds and payment issues.",
    system_prompt="You are the Billing Specialist.",
    tools=[process_refund],
    model="groq/qwen/qwen3-32b",
    api_key="sk-1234",
    base_url="http://localhost:9000/v1"
)

primary_agent = LiteLLMAgent(
    name="triage_agent",
    description="Primary user-facing agent that triages requests.",
    system_prompt="You are a helpful customer support triage agent.",
    tools=[],
    sub_agents=[account_agent, billing_agent],
    model="groq/qwen/qwen3-32b",
    api_key="sk-1234",
    base_url="http://localhost:9000/v1"
)

async def main():
    print("\nUser: I need a refund of $50 for user 321.")
    print("Agent: ", end="", flush=True)
    async for event in primary_agent.astream("I need a refund of $50 for user 321.",stream_events=True):
        if event["type"] == "content":
            print(event["delta"], end="", flush=True)
        elif event["type"] == "tool_start":
            print(f"\n[🔄 Thinking: Executing {event['name']}...]", end="", flush=True)
        elif event["type"] == "tool_end":
            print(f"\n[✅ Done: {event['name']} returned result]", end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
