import asyncio
import os
from litellm_adk import LiteLLMAgent, tool
from litellm_adk.memory.backends.postgres import PostgresVectorStore, PostgresVectorStoreConfig

# 1. Define tools
@tool
def get_weather(city: str):
    """Get the current weather for a city."""
    return f"The weather in {city} is mild and sunny."

async def main():
    # Use standard PG connection string
    connection_string = os.getenv("PG_URI", "postgresql://postgres:postgres@localhost:5433/postgres")
    
    print(f"Connecting to Postgres at {connection_string}...")
    
    try:
        # 2. Configured Vector Store with LiteLLM embedding using typed configuration model
        # Uses 'gemini/gemini-embedding-001' routed through the local LiteLLM proxy
        store_config = PostgresVectorStoreConfig(
            connection_string=connection_string,
            table_name="adk_memory_gemini",
            embedding_model=os.getenv("EMBEDDING_MODEL", "gemini/gemini-embedding-001"),
            vector_dim=int(os.getenv("EMBEDDING_DIM", "3072")),
            base_url=os.getenv("LITELLM_BASE_URL", "http://localhost:9000/v1"),
            api_key=os.getenv("LITELLM_API_KEY", "sk-1234"),
            custom_llm_provider="openai",
        )
        vector_store = PostgresVectorStore(config=store_config)
    except ImportError:
        print("⚠️  Skipping demo: 'asyncpg' or 'pgvector' not installed.")
        return
    except Exception as e:
        print(f"⚠️  Initialization failed: {e}")
        return

    # # 3. Seed Memory
    # print("--- 🧠 Vector Memory Demo ---")
    # facts = [
    #     "The user's favorite color is Emerald Green.",
    #     "The user lives in a penthouse in New York.",
    #     "The secret project code is 'Project Chimera'."
    # ]
    
    # try:
    #     print("Seeding memory with facts...")
    #     await vector_store.add_texts(facts)
    #     print("✅ Facts embedded and stored.")
    # except Exception as e:
    #     print(f"⚠️  Seeding notice: {e}")

    # 6. Initialize Agent with Vector Store
    # The Agent will automatically use vector_store.search(), which uses the custom provider.
    async with LiteLLMAgent(
        model="command-a-03-2025",
        api_key="sk-1234",
        base_url="http://localhost:9000/v1",
        vector_store=vector_store,
        vector_search_threshold=0.7, # Only include context if similarity score > 0.5
        tools=[get_weather],
        parallel_tool_calls=True,
        # fallbacks=["oci/xai.grok-3"],
        fallbacks=["command-a-03-2025"],
        system_prompt="You are a helpful assistant.",
    ) as agent:
        # 6. Query about the facts
        print("\n[User]: What is my favorite color? (First Call - DB Hit)")
        response1 = await agent.ainvoke("What is my favorite color?")
        print(f"[Agent]: {response1}")

        print("\n[User]: What is my favorite color? (Second Call - Cache Hit)")
        # This exact same prompt should trigger the LRU cache we just implemented
        response2 = await agent.ainvoke("What is my favorite color and where do I live?")
        print(f"[Agent]: {response2}")

if __name__ == "__main__":
    asyncio.run(main())
