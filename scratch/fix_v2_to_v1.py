import os
import re

EXAMPLES_DIR = r"d:\KiBO\litellm-adk\examples"

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Replace base_url="http://localhost:9000/v2" with base_url="http://localhost:9000/v1"
    content = content.replace('base_url="http://localhost:9000/v2"', 'base_url="http://localhost:9000/v1"')
    content = content.replace("base_url='http://localhost:9000/v2'", "base_url='http://localhost:9000/v1'")
    
    # Also fix yaml
    content = content.replace('base_url: http://localhost:9000/v2', 'base_url: http://localhost:9000/v1')

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {os.path.basename(filepath)}")

def main():
    for filename in os.listdir(EXAMPLES_DIR):
        if filename.endswith(".py") or filename.endswith(".yaml"):
            update_file(os.path.join(EXAMPLES_DIR, filename))

if __name__ == "__main__":
    main()
