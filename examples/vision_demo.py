import os
import asyncio
from litellm_adk import LiteLLMAgent

async def main():
    # Initialize an agent with a vision-capable model
    # Note: The agent now automatically handles URL fetching and MIME type correction!
    agent = LiteLLMAgent(
        name="VisionAssistant",
        model="openrouter/mistralai/ministral-3b-2512",
        api_key="sk-1234",
        base_url="http://localhost:9000/v1",
        system_prompt="You are a vision expert. Describe the images provided in detail."
    )

    # Use a public image URL directly
    # Even if the server returns incorrect MIME types (like 'binary/data'), 
    # the agent will auto-correct it using magic bytes.
    image_url = "https://4kwallpapers.com/images/wallpapers/tanjiro-kamado-2560x1440-10054.jpg"

    print(f"Vision Demo: {image_url}")

    print("\n--- [Sync Invoke] ---")
    # No extra methods needed - just pass the URL!
    response = agent.invoke(
        prompt="What anime character is in this image?",
        images=[image_url]
    )
    print(f"Response: {response.content}\n")

    print("--- [Async Invoke] ---")
    a_response = await agent.ainvoke(
        prompt="Describe the style and colors of this artwork.",
        images=[image_url]
    )
    print(f"Response: {a_response.content}\n")

    print("--- [Async Stream] ---")
    print("Streaming: ", end="", flush=True)
    async for chunk in agent.astream(
        prompt="What patterns do you see in the background?",
        images=[image_url]
    ):
        if isinstance(chunk, str):
            print(chunk, end="", flush=True)
        elif isinstance(chunk, dict) and chunk.get("type") == "content":
            print(chunk.get("delta", ""), end="", flush=True)
    print("\n")

if __name__ == "__main__":
    asyncio.run(main())
