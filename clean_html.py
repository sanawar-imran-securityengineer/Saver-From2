import os
import re

target_dir = r"c:\Users\7iha7\Music\New folder"

patterns_to_remove = [
    # Remove standalone nav links
    re.compile(r'\s*<a href="instagram\.html"[^>]*>Instagram</a>\s*', re.IGNORECASE),
    re.compile(r'\s*<a href="pinterest\.html"[^>]*>Pinterest</a>\s*', re.IGNORECASE),
    re.compile(r'\s*<a href="threads\.html"[^>]*>Threads</a>\s*', re.IGNORECASE),
    
    # Remove absolute nav/footer links
    re.compile(r'\s*<li><a href="/instagram"[^>]*>.*?</a></li>\s*', re.IGNORECASE),
    re.compile(r'\s*<li><a href="/pinterest"[^>]*>.*?</a></li>\s*', re.IGNORECASE),
    re.compile(r'\s*<li><a href="/threads"[^>]*>.*?</a></li>\s*', re.IGNORECASE),
    re.compile(r'\s*<li><a href="/pages/instagram\.html"[^>]*>.*?</a></li>\s*', re.IGNORECASE),
    re.compile(r'\s*<li><a href="/pages/pinterest\.html"[^>]*>.*?</a></li>\s*', re.IGNORECASE),
    re.compile(r'\s*<li><a href="/pages/threads\.html"[^>]*>.*?</a></li>\s*', re.IGNORECASE),

    # Remove JS PLATFORMS object entries
    re.compile(r'\s*instagram:\s*\{.*?\},?', re.IGNORECASE),
    re.compile(r'\s*pinterest:\s*\{.*?\},?', re.IGNORECASE),
    re.compile(r'\s*threads:\s*\{.*?\},?', re.IGNORECASE),
]

# Patterns for HTML blocks (like cards or buttons)
block_patterns = [
    # Match platform cards in index.html starting from comments like <!-- 3. Instagram --> to the end of its div
    re.compile(r'\s*<!--\s*\d+\.\s*Instagram\s*-->\s*<div class="platform-card" data-platform="instagram".*?</div>\s*</div>\s*', re.IGNORECASE | re.DOTALL),
    re.compile(r'\s*<!--\s*\d+\.\s*Pinterest\s*-->\s*<div class="platform-card" data-platform="pinterest".*?</div>\s*</div>\s*', re.IGNORECASE | re.DOTALL),
    re.compile(r'\s*<!--\s*\d+\.\s*Threads\s*-->\s*<div class="platform-card" data-platform="threads".*?</div>\s*</div>\s*', re.IGNORECASE | re.DOTALL),

    # Gateway specific items (buttons)
    re.compile(r'\s*<button class="platform-tab-btn" data-filter="instagram">.*?</button>\s*', re.IGNORECASE),
    re.compile(r'\s*<button class="platform-tab-btn" data-filter="pinterest">.*?</button>\s*', re.IGNORECASE),
    re.compile(r'\s*<button class="platform-tab-btn" data-filter="threads">.*?</button>\s*', re.IGNORECASE),
    
    # Additional generic block removal if we know the start/end tag bounds, but regex can be tricky with nested divs.
    # We will try to match `<div class="platform-card" data-platform="instagram"` up to its closing tag carefully.
    re.compile(r'\s*<div class="platform-card" data-platform="(instagram|pinterest|threads)".*?</a>\s*</div>\s*</div>\s*', re.IGNORECASE | re.DOTALL)
]


def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    for pattern in patterns_to_remove:
        content = pattern.sub('\n', content)
        
    for pattern in block_patterns:
        content = pattern.sub('\n', content)
        
    # Extra fix up: multiple newlines to single
    # content = re.sub(r'\n{3,}', '\n\n', content)

    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Cleaned {filepath}")

for root, dirs, files in os.walk(target_dir):
    if '.git' in root or 'node_modules' in root or 'venv' in root or '.venv' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            clean_file(os.path.join(root, file))
