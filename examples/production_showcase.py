import asyncio
import os
import uuid
from litellm_adk import LiteLLMAgent, tool
from litellm_adk.memory import SQLAlchemyMemory
from litellm_adk.observability import adk_logger

# 1. SETUP: Persistent Scalable Memory (SQLAlchemy)
# Using SQLite locally, but easily swaps to Postgres via connection string.
DB_PATH = "production_memory.db"
memory = SQLAlchemyMemory(f"sqlite+aiosqlite:///{DB_PATH}")

# 2. DEFINE RESILIENT TOOLS with Timeouts and Error Policies
@tool
async def get_weather_data(location: str):
    """Fetches highly accurate weather data for a location."""
    adk_logger.info(f"Fetching weather for {location}...")
    # await asyncio.sleep(1) # Simulate network latency
    return {"location": location, "condition": "Sunny", "temp": 28}


async def main():
    # 3. INITIALIZE PRODUCTION AGENT
    # Using LiteLLM failover pattern and Vision-capable model
    agent = LiteLLMAgent(
        base_url="http://localhost:9000/v2",
        api_key="sk-1234",
        model="groq/qwen/qwen3-32b",
        memory=memory,
        tools=[get_weather_data],
        parallel_tool_calls=False
    )

    # 4. HEALTH CHECK (Critical for Kubernetes/Production pod startup)
    health = await agent.check_health()
    print(f"\n[SYSTEM] Health Status: {health['status'].upper()}")
    print(f"[SYSTEM] Components: {health['components']}\n")

    # 5. MULTIMODAL PRODUCTION TURN
    # Demonstration of the automated VisionOptimizer
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    image_url = "https://motionbgs.com/media/1060/tanjiro-kamado-with-katana-in-circle.jpg"
    
    prompt = (
        "Check the weather in Mumbai. Then transition to looking at this image. "
        "Does the weather data (Sunny) match the visuals? "
    )

    print(f"--- PROMPT ---\n{prompt}\n")

    response = await agent.ainvoke(
        prompt=prompt,
        images=[image_url],
        session_id=session_id
    )

    # 6. OUTPUT & PRODUCTION ANALYTICS
    print(f"--- AGENT RESPONSE ---\n{response.content}\n")
    
    print("--- PRODUCTION METRICS ---")
    print(f"Session ID: {response.session_id}")
    print(f"Prompt Tokens: {response.usage.prompt_tokens}")
    print(f"Completion Tokens: {response.usage.completion_tokens}")
    print(f"Total Tokens Used: {response.usage.total_tokens}")
    print(f"Estimated Cost (USD): ${response.usage.cost:.6f}")
    
    # 7. CLEANUP
    await memory.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH) # Cleanup for demo
        adk_logger.info("Demo database cleaned up.")

if __name__ == "__main__":
    # Optional: Enable production observability (uncomment to see JSON logs)
    # os.environ["ADK_LOG_FORMAT"] = "json"
    # os.environ["ADK_ENABLE_TELEMETRY"] = "True"
    
    asyncio.run(main())
