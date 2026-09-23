import os
import re

target_dir = r"c:\Users\7iha7\Music\New folder\frontend"

missing_alt = 0
total_images = 0

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # find all img tags
            imgs = re.findall(r'<img[^>]*>', content, re.IGNORECASE)
            for img in imgs:
                total_images += 1
                if 'alt=' not in img.lower():
                    missing_alt += 1
                    print(f"Missing alt in {file}: {img}")

print(f"Total images checked: {total_images}")
print(f"Total missing alt: {missing_alt}")
