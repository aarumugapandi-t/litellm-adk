import asyncio
from litellm_adk import Agent, tool

# 1. Define a tool using the @tool decorator
@tool(description="Calculates compound interest on an investment.")
def calculate_compound_interest(principal: float, rate_pct: float, years: int) -> dict:
    rate = rate_pct / 100.0
    final_amount = principal * ((1 + rate) ** years)
    interest_earned = final_amount - principal
    return {
        "principal": principal,
        "final_amount": round(final_amount, 2),
        "interest_earned": round(interest_earned, 2),
        "years": years,
    }

async def main():
    # 2. Instantiate the agent
    agent = Agent(
        name="FinancialAdvisoryAgent",
        model="groq/openai/gpt-oss-120b",  # or "claude-3-5-sonnet", "ollama/llama3", etc.
        base_url="http://localhost:9000/v1",  # Replace with your actual base URL
        api_key="sk-1234",  # Replace with your actual
        system_prompt="You are a professional financial advisor. Use your tools for precise computations.",
        tools=[calculate_compound_interest],
        # parallel_tool_calls=True,  # Allow parallel execution of tools
    )

    # 3. Invoke the agent
    response = await agent.ainvoke(
        "If I invest $10,000 and my friend invest $20,000 at a 7.5% annual rate for 10 years, how much will I have?"
    )

    print("Agent Response:\n", response.text)
    print("\nTools Called:")
    for tc in response.tool_calls:
        print(f"- {tc.name}({tc.arguments}) -> {tc.result}")

if __name__ == "__main__":
    asyncio.run(main())
