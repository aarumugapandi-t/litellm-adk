import os
import re

EXAMPLES_DIR = r"d:\KiBO\litellm-adk\examples"

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Replace model="something" with model="groq/qwen/qwen3-32b"
    # Or model='something'
    content = re.sub(r'model\s*=\s*["\'][a-zA-Z0-9/\.\-]+["\']', 'model="groq/qwen/qwen3-32b"', content)

    # Inject base_url into LiteLLMAgent(
    # Only if base_url is not already there
    if 'base_url=' not in content:
        content = re.sub(
            r'LiteLLMAgent\(',
            r'LiteLLMAgent(\n    base_url="http://localhost:9000/v2",',
            content
        )
    else:
        # replace existing base_url
        content = re.sub(r'base_url\s*=\s*["\'][^"\']+["\']', 'base_url="http://localhost:9000/v2"', content)

    # Some examples might define model in a config dict or AgentConfig
    content = re.sub(r'"model"\s*:\s*["\'][a-zA-Z0-9/\.\-]+["\']', '"model": "groq/qwen/qwen3-32b"', content)
    content = re.sub(r"'model'\s*:\s*['\"][a-zA-Z0-9/\.\-]+['\"]", "'model': 'groq/qwen/qwen3-32b'", content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {os.path.basename(filepath)}")

def main():
    for filename in os.listdir(EXAMPLES_DIR):
        if filename.endswith(".py"):
            update_file(os.path.join(EXAMPLES_DIR, filename))

if __name__ == "__main__":
    main()
