import os
import re
from urllib.parse import quote

target_dir = r"c:\Users\7iha7\Music\New folder"
domain = "https://saverfrom.com"

# The URLs that should be in the sitemap
sitemap_urls = [
    "/",
    "/youtube",
    "/tiktok",
    "/facebook",
    "/twitter",
    "/snapchat",
    "/reddit",
    "/twitch",
    "/about",
    "/blog",
    "/contact",
    "/copyright",
    "/disclaimer",
    "/privacy-policy",
    "/terms-of-service",
]

def generate_sitemap(directory):
    sitemap_path = os.path.join(directory, "sitemap.xml")
    content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in sitemap_urls:
        content += f'  <url>\n    <loc>{domain}{url}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>{1.0 if url == "/" else 0.8}</priority>\n  </url>\n'
    content += '</urlset>'
    
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(content)

def generate_robots(directory):
    robots_path = os.path.join(directory, "robots.txt")
    content = f"User-agent: *\nDisallow: /api/\nDisallow: /backend/\n\nSitemap: {domain}/sitemap.xml\n"
    with open(robots_path, "w", encoding="utf-8") as f:
        f.write(content)

def process_html_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if "<head>" not in content:
        return

    # Extract title and description for OG tags
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    desc_match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', content, re.IGNORECASE)
    
    title = title_match.group(1) if title_match else "SaverFrom - Video Downloader"
    desc = desc_match.group(1) if desc_match else "Download videos easily from multiple platforms."
    
    # Determine the relative URL
    rel_path = filepath.replace(target_dir, "").replace("\\", "/")
    # strip prefix folders to guess URL
    if "/frontend/pages/" in rel_path:
        url_path = rel_path.split("/frontend/pages")[1].replace(".html", "")
        if not url_path.startswith("/"):
            url_path = "/" + url_path
    elif "/frontend/index.html" in rel_path:
        url_path = "/"
    else:
        url_path = "/" + os.path.basename(filepath)

    full_url = domain + url_path

    seo_tags = f"""
  <!-- SEO & Social Meta Tags injected by script -->
  <link rel="canonical" href="{full_url}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{full_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="SaverFrom" />
  <meta property="og:image" content="{domain}/static/icons/saverfrom-logo.svg" />
  
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{desc}" />
  <meta name="twitter:image" content="{domain}/static/icons/saverfrom-logo.svg" />
  <meta name="keywords" content="video downloader, download video, youtube downloader, tiktok downloader, facebook downloader" />
"""

    schema_jsonld = f"""
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "SaverFrom",
    "url": "{domain}",
    "potentialAction": {{
      "@type": "SearchAction",
      "target": "{domain}/?url={{search_term_string}}",
      "query-input": "required name=search_term_string"
    }}
  }}
  </script>
"""

    # Add tags if not already present
    if "og:title" not in content:
        # inject just before </head>
        content = content.replace("</head>", f"{seo_tags}</head>", 1)
        
    if "application/ld+json" not in content and url_path == "/":
        content = content.replace("</head>", f"{schema_jsonld}</head>", 1)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


print("Generating sitemap and robots.txt in frontend and standalone-frontend")
frontend_dirs = [
    os.path.join(target_dir, "frontend"),
    os.path.join(target_dir, "main-platform", "frontend"),
    os.path.join(target_dir, "standalone-frontend")
]

for d in frontend_dirs:
    if os.path.exists(d):
        generate_sitemap(d)
        generate_robots(d)

print("Injecting SEO tags into HTML files")
for root, dirs, files in os.walk(target_dir):
    if '.git' in root or 'node_modules' in root or 'venv' in root or '.venv' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            process_html_file(os.path.join(root, file))

print("SEO tags successfully injected!")
