import asyncio
import litellm

async def main():
    try:
        litellm.set_verbose=True
        # Test 1: openai proxy with v1
        await litellm.acompletion(
            model="openai/groq/qwen/qwen3-32b",
            api_base="http://localhost:9000/v1",
            api_key="sk-1234",
            messages=[{"role": "user", "content": "hello"}]
        )
        print("SUCCESS")
    except Exception as e:
        print(f"Error 1: {e}")

if __name__ == "__main__":
    asyncio.run(main())
