import os
import re

examples_dir = r"d:\KiBO\litellm-adk\examples"

model_regex = re.compile(r'model\s*=\s*["\'][^"\']+["\']')
base_url_regex = re.compile(r'base_url\s*=\s*["\'][^"\']+["\']')

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'model=' not in content and 'model =' not in content:
        return

    new_content = model_regex.sub('model="groq/qwen/qwen3-32b"', content)

    if new_content == content:
        return
        
    if base_url_regex.search(new_content):
        new_content = base_url_regex.sub('base_url="http://localhost:9000/v2"', new_content)
    else:
        new_content = re.sub(r'(model="groq/qwen/qwen3-32b")', r'\1, base_url="http://localhost:9000/v2"', new_content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

for root, _, files in os.walk(examples_dir):
    for file in files:
        if file.endswith('.py'):
            process_file(os.path.join(root, file))

print("Updated all examples.")
