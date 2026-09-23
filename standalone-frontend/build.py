import os
import re

html_content = open('index.html', 'r', encoding='utf-8').read()

info_pages = {
    'about': 'About Us',
    'privacy-policy': 'Privacy Policy',
    'terms': 'Terms of Service'
}

for filename, title in info_pages.items():
    content = html_content.replace('VidSaver - Universal Free Video Downloader', f'{title} - VidSaver')
    content = content.replace('✨ Universal Media Hub', 'VidSaver Info')
    content = re.sub(r'Download Any Video in <br />\s*<span class="gradient-text">Highest Quality & MP3</span>', title, content)
    content = content.replace('Just paste the link below and download instantly. Support for YouTube, Instagram, TikTok, Facebook, Reddit, and more.', f'This is the {title} page for VidSaver.')
    content = re.sub(r'<div class="downloader-container">[\s\S]*?</div>\s*</div>', f'<div class="downloader-container"><div class="downloader-box" style="color:white;text-align:center;padding:50px;">Content for {title} goes here.</div></div>', content, flags=re.DOTALL)
    
    with open(f'{filename}.html', 'w', encoding='utf-8') as f:
        f.write(content)
