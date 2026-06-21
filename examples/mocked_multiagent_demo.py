"""
Mocked Multi-Agent Orchestration Demo

This script demonstrates how LiteLLM ADK handles sub-agent delegation.
It uses `unittest.mock` to simulate LLM responses so it runs entirely offline
without needing any API keys.
"""

import asyncio
from litellm_adk.agents import LiteLLMAgent
from litellm_adk.tools import tool

# --- 1. Define Tools for Sub-Agents ---

@tool
def get_user_data(user_id: str):
    """Fetch profile data for a specific user ID."""
    print(f"\n[Tool Executing] get_user_data for {user_id}...")
    return f"User {user_id} is a premium member with 5 active subscriptions."

@tool
def process_refund(user_id: str, amount: float):
    """Process a refund for a user."""
    print(f"\n[Tool Executing] process_refund for {user_id} / ${amount}...")
    return f"Successfully refunded ${amount} to user {user_id}."

# --- 2. Create Specialized Sub-Agents ---

account_agent = LiteLLMAgent(
    name="account_management_agent",
    description="Handles user account queries, profile lookups, and basic account info.",
    system_prompt="You are the Account Management Specialist.",
    tools=[get_user_data],
    model="groq/qwen/qwen3-32b", base_url="http://localhost:9000/v1",
    api_key="sk-1234",
)

billing_agent = LiteLLMAgent(
    name="billing_agent",
    description="Handles refunds, charges, and payment related issues.",
    system_prompt="You are the Billing Specialist.",
    tools=[process_refund],
    model="groq/qwen/qwen3-32b", base_url="http://localhost:9000/v1",
    api_key="sk-1234",
)

# --- 3. Create Primary "Supervisor" Agent ---

primary_agent = LiteLLMAgent(
    name="triage_agent",
    description="Primary user-facing agent that triages requests.",
    system_prompt="You are a helpful customer support triage agent.",
    sub_agents=[account_agent, billing_agent],
    model="groq/qwen/qwen3-32b", base_url="http://localhost:9000/v1",
    api_key="sk-1234",
)

async def main():
    print("\n--- Multiagent Triage Demo ---")
    
    # --- SCENARIO 1: User asks for a refund ---
    print("\nUser: I need a refund of $50 for user 123. And tell me about user 123 too")
    
    response = await primary_agent.ainvoke("I need a refund of $50 for user 123. And tell me about user 123 too")
    print(f"\nFinal Agent Output: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
