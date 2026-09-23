import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from .router import router as api_router

# Determine the project root (two levels up from this file)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
PAGES_DIR = os.path.join(FRONTEND_DIR, "pages")

app = FastAPI(title="Unified Downloader Gateway")

# Include the API router first
app.include_router(api_router)

# Friendly convenience shortcuts
@app.get("/downloader")
async def to_dl(): return RedirectResponse(url="/#downloader-section", status_code=301)

def serve_page(page_name):
    path = os.path.join(PAGES_DIR, f"{page_name}.html")
    if os.path.exists(path):
        return FileResponse(path)
    return RedirectResponse(url="/", status_code=301)

@app.get("/youtube")
async def to_yt(): return serve_page("youtube")
@app.get("/tiktok")
async def to_tt(): return serve_page("tiktok")
@app.get("/instagram")
async def to_ig(): return serve_page("instagram")
@app.get("/facebook")
async def to_fb(): return serve_page("facebook")
@app.get("/twitter")
async def to_tw(): return serve_page("twitter")
@app.get("/snapchat")
async def to_sc(): return serve_page("snapchat")
@app.get("/pinterest")
async def to_pin(): return serve_page("pinterest")
@app.get("/reddit")
async def to_red(): return serve_page("reddit")
@app.get("/threads")
async def to_thr(): return serve_page("threads")
@app.get("/twitch")
async def to_twt(): return serve_page("twitch")
@app.get("/blog")
async def to_blog(): return serve_page("blog")
@app.get("/about")
async def to_about(): return serve_page("about")
@app.get("/contact")
async def to_contact(): return serve_page("contact")
@app.get("/privacy-policy")
async def to_privacy(): return serve_page("privacy-policy")
@app.get("/terms-of-service")
async def to_terms(): return serve_page("terms-of-service")
@app.get("/copyright")
async def to_copyright(): return serve_page("copyright")
@app.get("/disclaimer")
async def to_disclaimer(): return serve_page("disclaimer")

# Mount static and pages if they exist
static_dir = os.path.join(FRONTEND_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static_assets")

pages_dir = os.path.join(FRONTEND_DIR, "pages")
if os.path.exists(pages_dir):
    app.mount("/pages", StaticFiles(directory=pages_dir, html=True), name="pages")

# Mount the frontend static files. ``html=True`` serves index.html
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
