import asyncio
from litellm_adk.agent import LiteLLMAgent
from litellm_adk.security import PIIScrubber

async def main():
    print("=== PII Security Demo ===")
    
    # Enable PII scrubbing
    agent = LiteLLMAgent(
        name="SecureAgent",
        system_prompt="You are a secure assistant. Summarize what the user told you, being careful not to leak their personal data.",
        model="groq/qwen/qwen3-32b",
        base_url="http://localhost:9000/v1",
        scrub_pii=True,
        api_key="sk-1234"
    )
    
    user_input = "Hello, my name is John and my SSN is 123-45-6789. Also my credit card is 1234-5678-9012-3456 and email is john.doe@example.com."
    
    print(f"\nUser Input: {user_input}")
    print("\nSending to agent... (The LLM will only see redacted data)")
    
    response = await agent.ainvoke(user_input)
    
    print(f"\nAgent Response:\n{response.content}")
    print("\nNotice that the LLM was entirely unaware of the actual SSN, Email, or Credit Card!")

if __name__ == "__main__":
    asyncio.run(main())
