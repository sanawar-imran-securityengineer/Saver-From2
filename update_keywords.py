import os, re
target_dir = r'c:\Users\7iha7\Music\New folder'

keywords_map = {
    'youtube.html': 'youtube video downloader, download youtube shorts, youtube to mp4, youtube mp3',
    'tiktok.html': 'tiktok video downloader, download tiktok without watermark, save tiktok video',
    'facebook.html': 'facebook video downloader, fb video download, facebook reel download',
    'twitter.html': 'twitter video downloader, x video downloader, save twitter video',
    'snapchat.html': 'snapchat video downloader, download snapchat spotlight, save snapchat video',
    'reddit.html': 'reddit video downloader, reddit video with audio, save reddit video',
    'twitch.html': 'twitch clip downloader, download twitch vod, save twitch video',
    'instagram.html': 'instagram video downloader, download instagram reels, ig downloader'
}

for root, dirs, files in os.walk(target_dir):
    if '.git' in root or 'node_modules' in root or 'venv' in root or '.venv' in root: continue
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find appropriate keywords
            kw = keywords_map.get(file, 'free video downloader, fast video downloader, download video online, mp4 downloader')
            if file == 'index.html':
                kw = 'video downloader, free video downloader, download video from any site, youtube downloader, tiktok downloader without watermark'
            
            # Replace keywords
            content = re.sub(
                r'<meta name=\"keywords\" content=\".*?\" />',
                f'<meta name=\"keywords\" content=\"{kw}\" />',
                content
            )
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
print('Updated keywords.')
