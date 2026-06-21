import asyncio
import litellm

async def main():
    try:
        litellm.set_verbose=True
        # Test 1: groq provider
        await litellm.acompletion(
            model="groq/qwen/qwen3-32b",
            api_base="http://localhost:9000/v2",
            messages=[{"role": "user", "content": "hello"}]
        )
    except Exception as e:
        print(f"Error 1: {e}")

if __name__ == "__main__":
    asyncio.run(main())
