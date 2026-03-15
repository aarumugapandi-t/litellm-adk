"""
Multiagent Demo using Sub-Agents (Swarm/Hierarchical Pattern)

This demo shows how a primary agent can dynamically route queries 
to specialized sub-agents natively using the LiteLLM ADK.
"""
import os
import asyncio
from dotenv import load_dotenv
from litellm_adk.agents import LiteLLMAgent
from litellm_adk.tools import tool

load_dotenv()

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
    system_prompt="You are the Account Management Specialist. Use your tools to answer user account queries.",
    tools=[get_user_data],
    model="command-a-03-2025",
    api_key="sk-1234",
    base_url="http://localhost:9000/v1"
)

billing_agent = LiteLLMAgent(
    name="billing_agent",
    description="Handles refunds, charges, and payment related issues.",
    system_prompt="You are the Billing Specialist. Handle refunds and payment inquiries safely.",
    tools=[process_refund],
    model="command-a-03-2025",
    api_key="sk-1234",
    base_url="http://localhost:9000/v1"
)

# --- 3. Create Primary "Supervisor" Agent ---
# We inject the sub-agents into the primary agent. 
# It will automatically get tools like `transfer_to_account_management_agent` and `transfer_to_billing_agent`.

primary_agent = LiteLLMAgent(
    name="triage_agent",
    description="Primary user-facing agent that triages requests.",
    system_prompt="You are a helpful customer support triage agent. You greet the user, determine their need, and transfer them to the appropriate specialist agent if you cannot answer the request directly.",
    sub_agents=[account_agent, billing_agent],
    model="openrouter/anthropic/claude-3-haiku",
    api_key="sk-1234",
    base_url="http://localhost:9000/v1"
)

async def main():
    print("\n--- Multiagent Triage Demo ---")
    
    # 1. Ask a question meant for the Account Agent
    print("\nUser: Can you check the profile for user 123?")
    response = await primary_agent.ainvoke("Can you check the profile for user 123?")
    print(f"\nAgent: {response.content}")
    
    # 2. Ask a question meant for the Billing Agent
    print("\nUser: I need a refund of $50 for user 123.")
    response = await primary_agent.ainvoke("I need a refund of $50 for user 123.")
    print(f"\nAgent: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
