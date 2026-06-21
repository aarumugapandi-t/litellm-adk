import asyncio
from litellm_adk import LiteLLMAgent

# 1. Initialize the agent and bind it to your litellm proxy server
agent = LiteLLMAgent(
        model="groq/qwen/qwen3-32b", # Configured model name
        api_key="sk-1234", # Litellm's vitual key 
        base_url="http://localhost:9000/v1", # Litellm server endpoint
        system_prompt="You are a helpful coding assistant."
    )
    
# 2. Invoke the agent. Context and memory are handled automatically!
response = agent.invoke("Write a quick python script to reverse a string.")
    
print(response.content)