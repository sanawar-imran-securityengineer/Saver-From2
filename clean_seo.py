import os
import re

target_dir = r"c:\Users\7iha7\Music\New folder"

for root, dirs, files in os.walk(target_dir):
    if '.git' in root or 'node_modules' in root or 'venv' in root or '.venv' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            if "<!-- SEO & Social Meta Tags injected by script -->" in content:
                # Remove the block
                content = re.sub(r'<!-- SEO & Social Meta Tags injected by script -->.*?(?=</head>)', '', content, flags=re.DOTALL)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Cleaned {filepath}")
