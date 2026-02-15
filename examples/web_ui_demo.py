import asyncio
from litellm_adk import LiteLLMAgent, tool

@tool
def get_funny_fact():
    """Returns a random funny fact."""
    return "A cloud can weigh more than a million pounds."

@tool
def calculate_area(radius: float):
    """Calculates the area of a circle."""
    import math
    return f"Area: {math.pi * radius**2}"

def main():
    from litellm_adk import FileMemory
    
    # Initialize the agent
    agent = LiteLLMAgent(
        model="oci/xai.grok-3-mini",
        api_key="sk-1234",
        base_url="http://localhost:4000/v1",
        system_prompt="You are a helpful UI demo assistant. You have access to tools.",
        tools=[get_funny_fact, calculate_area],
        memory=FileMemory("web_ui_history.json")
    )

    # Launch the Web UI
    agent.run(port=8080)

if __name__ == "__main__":
    main()
