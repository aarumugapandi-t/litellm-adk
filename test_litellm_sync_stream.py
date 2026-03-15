import os
import litellm
from dotenv import load_dotenv

load_dotenv()

# Use the same settings as the working async demo
PROXY_URL = "http://localhost:9000/v1"
API_KEY = "sk-1234"

def test_sync_stream():
    messages = [{"role": "user", "content": "Say hello world"}]
    print("Testing sync stream...")
    try:
        response = litellm.completion(
            model="openai/command-a-03-2025",
            messages=messages,
            api_key=API_KEY,
            base_url=PROXY_URL,
            stream=True
        )
        print("Got response object:", type(response))
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
        print("\nSync stream complete.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_sync_stream()
