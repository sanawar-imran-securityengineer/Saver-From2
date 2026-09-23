import os
import glob

# The directory containing the HTML files
frontend_dir = r"main-platform\frontend\pages"

# All platform HTML files (excluding those we don't want to touch, but the user said "all video downloaders", so we will change them all except about, blog, etc.)
files_to_patch = [
    "facebook.html",
    "instagram.html",
    "pinterest.html",
    "reddit.html",
    "snapchat.html",
    "threads.html",
    "twitch.html",
    "twitter.html",
    "youtube.html"
]

for filename in files_to_patch:
    filepath = os.path.join(frontend_dir, filename)
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Replace fetch('/api/v1/download' with fetch('/api/v1/download-file'
    content = content.replace("fetch('/api/v1/download', {", "fetch('/api/v1/download-file', {")

    # 2. Replace the proxy-download logic
    old_proxy_logic = "const directDlUrl = '/api/v1/proxy-download?url=' + encodeURIComponent(rawDlUrl) + '&filename=' + encodeURIComponent(filename);"
    new_proxy_logic = "const directDlUrl = data && data.download_url ? data.download_url : rawDlUrl;"
    
    content = content.replace(old_proxy_logic, new_proxy_logic)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Patched files successfully.")
