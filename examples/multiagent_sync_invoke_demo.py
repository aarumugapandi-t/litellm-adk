import os
import sys
from dotenv import load_dotenv
from litellm_adk.core.agent import LiteLLMAgent
from litellm_adk.tools.registry import tool

load_dotenv()

# Use the same settings as the working async demo
PROXY_URL = "http://localhost:9000/v1"
API_KEY = "sk-1234"

# Define a billing specialist agent
billing_agent = LiteLLMAgent(
    name="billing_agent_specialist",
    description="Handles refunds and payment issues.",
    model="openrouter/anthropic/claude-3-haiku",
    api_key=API_KEY,
    base_url=PROXY_URL,
    system_prompt="You are the Billing Specialist. If a user asks for a refund, use the process_refund tool."
)

@tool
def process_refund(user_id: str, amount: float) -> str:
    """Processes a refund for a specific user and amount."""
    return f"Successfully refunded ${amount} to user {user_id} via billing specialist."

# Add the tool to the billing agent
billing_agent.tools.append(process_refund)

# Define the supervisor agent
supervisor = LiteLLMAgent(
    name="triage_agent",
    description="Primary user-facing agent that triages requests.",
    model="command-a-03-2025",
    api_key=API_KEY,
    base_url=PROXY_URL,
    sub_agents=[billing_agent],
    system_prompt="You are a helpful customer support triage agent. Use transfer_to_billing_agent_specialist if the user has a billing or refund request."
)

def main():
    user_input = "I need a refund of $50 for user 321."
    print(f"\nUser: {user_input}")
    print("Agent: ", end="", flush=True)

    try:
        # Use the synchronous invoke method
        response = supervisor.invoke(user_input)
        print(response.content)
    except Exception as e:
        print(f"\nERROR: {e}")
    
    print("\n\nDemo complete (Sync Invoke).")

if __name__ == "__main__":
    main()
