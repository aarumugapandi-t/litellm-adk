from requests import api
import asyncio
import time
from litellm_adk.agent import LiteLLMAgent
from litellm_adk.caching import CacheManager
from litellm_adk.observability.telemetry import setup_litellm_telemetry

async def main():
    print("=== Semantic Caching & Telemetry Demo ===")
    
    # 1. Enable OpenTelemetry observability
    setup_litellm_telemetry()
    print("Telemetry hooked to OpenTelemetry/Langfuse.")

    # 2. Enable Semantic Caching (Dragonfly / Redis)
    # Note: Requires a running Redis or Dragonfly instance on localhost:6379
    # Semantic caching uses an embedding model (OpenAI by default) to determine vector dimensions.
    try:
        CacheManager.enable_redis_cache(host="127.0.0.1", port=6379, semantic=True)
        print("Semantic Caching enabled.")
    except Exception as e:
        print(f"\n[Warning] Could not enable semantic caching: {e}")
        print("If this is an API Key error, remember that Semantic Caching requires an embedding API key (e.g. OPENAI_API_KEY)!")
        print("Falling back to Exact-Match Caching...\n")
        CacheManager.enable_redis_cache(host="127.0.0.1", port=6379, semantic=False)
        print("Exact-Match Caching enabled.")
    
    agent = LiteLLMAgent(
        name="CacheAgent",
        system_prompt="You are a helpful assistant.",
        model="groq/qwen/qwen3-32b",
        base_url="http://localhost:9000/v1",
        api_key="sk-1234"
    )
    
    query = "Explain the theory of relativity in exactly 3 sentences."
    
    print(f"\nQuery: {query}")
    print("Sending first request (Uncached)...")
    
    start = time.time()
    response1 = await agent.ainvoke(query)
    end = time.time()
    
    print(f"\nResponse 1 (Took {end - start:.2f}s):\n{response1.content}")
    
    print("\nSending second request (Should be Cached)...")
    start = time.time()
    response2 = await agent.ainvoke(query)
    end = time.time()
    
    print(f"\nResponse 2 (Took {end - start:.2f}s):\n{response2.content}")
    print("\nNotice the time difference. The second query was served instantaneously from the cache!")

if __name__ == "__main__":
    asyncio.run(main())
