import os
import re

file = r'c:\Users\7iha7\Music\New folder\main-platform\gateway\static\index.html'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'<p\s+class="hero-subtitle">.*?</p>', '', content, flags=re.DOTALL)
content = re.sub(r'<div\s+class="platform-tags"[^>]*>.*?</div>', '', content, flags=re.DOTALL)

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
