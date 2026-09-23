import os, re
filepath = r'c:\Users\7iha7\Music\New folder\frontend\index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

schema_addition = """
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "OmniDownloader",
    "operatingSystem": "All",
    "applicationCategory": "MultimediaApplication",
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD"
    }
  }
  </script>
"""

if "SoftwareApplication" not in content:
    content = content.replace("</head>", schema_addition + "</head>")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Schema added")
else:
    print("Schema already present")
