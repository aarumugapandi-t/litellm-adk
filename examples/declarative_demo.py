import asyncio
from litellm_adk.agent import LiteLLMAgent
from litellm_adk.tools.registry import tool_registry

# 1. Define tools normally
@tool_registry.register()
def check_inventory(item_id: str) -> str:
    """Check the inventory for a specific item."""
    return f"Item {item_id} has 50 units in stock."

@tool_registry.register()
def process_order(item_id: str, quantity: int) -> str:
    """Process an order for an item."""
    return f"Successfully ordered {quantity} of {item_id}."

# 2. Define our multi-agent architecture entirely in YAML
yaml_config = """
name: SupervisorAgent
description: Triages user requests to specialists
model: groq/qwen/qwen3-32b
api_key: sk-1234
base_url: http://localhost:9000/v1
system_prompt: |
  You are the primary triage agent.
  If the user asks about stock or inventory, transfer them to the InventoryAgent.
  If the user wants to buy something, transfer them to the OrderAgent.
  Otherwise, help them politely.

sub_agents:
  - name: InventoryAgent
    description: Handles inventory queries
    model: groq/qwen/qwen3-32b
    base_url: http://localhost:9000/v1
    api_key: sk-1234
    system_prompt: "You are the inventory specialist. Use the check_inventory tool."
    tools: ["check_inventory"]
    
  - name: OrderAgent
    description: Handles order processing
    model: groq/qwen/qwen3-32b
    base_url: http://localhost:9000/v1
    api_key: sk-1234
    system_prompt: "You are the order processing specialist. Use the process_order tool."
    tools: ["process_order"]
"""

async def main():
    # 3. Initialize the entire tree with a single line!
    supervisor = LiteLLMAgent.from_yaml(yaml_config)
    
    print(f"Loaded Supervisor: {supervisor.name} with {len(supervisor.sub_agents)} sub-agents.")
    print("Available Tools on Supervisor:", [t["function"]["name"] for t in supervisor.tools])
    
    print("\n--- Example 1: Checking Inventory (Handoff to InventoryAgent) ---")
    response1 = await supervisor.ainvoke("Do you have item 123 in stock?")
    print(f"Final Response: {response1.content}")

    print("\n--- Example 2: Placing an Order (Handoff to OrderAgent) ---")
    response2 = await supervisor.ainvoke("I'd like to order 5 units of item 123.")
    print(f"Final Response: {response2.content}")

if __name__ == "__main__":
    asyncio.run(main())
