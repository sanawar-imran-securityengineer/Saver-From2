"""SaverFrom — unified video downloader backend.

One FastAPI application that replaces the original microservice gateway. Every
downloader runs **in-process**, which is what makes the project deployable on
Hostinger (no second server, no ports 8001-8010).

Run locally:
    uvicorn backend.main:app --reload --port 8000

Run in production:
    uvicorn backend.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routers import ALL_ROUTERS, EXTRA_PAGES, PLATFORM_PAGES
from .routers.health import register_cleanup_service
from .utils.cache import cache
from .utils.cleanup import FileCleanupService
from .utils.config import FRONTEND_DIR, settings
from .utils.security import setup_logging

setup_logging(logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger("saverfrom.main")

cleanup_service = FileCleanupService(settings.DOWNLOADS_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the background services."""
    await cache.connect()
    cleanup_service.start()
    register_cleanup_service(cleanup_service)
    logger.info(
        "%s v%s starting — env=%s downloads=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.DOWNLOADS_DIR,
    )
    try:
        yield
    finally:
        await cleanup_service.stop()
        await cache.disconnect()
        logger.info("%s stopped", settings.APP_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        description=(
            "Unified multi-platform video downloader API. "
            "Accepts public media URLs; no API keys required."
        ),
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        root_path=settings.ROOT_PATH or "",
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    # GZip keeps the JSON metadata responses small over slow mobile links.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # CORS is driven entirely by CORS_ORIGINS so development ("*") and
    # production (explicit domain list) are configured the same way.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Length"],
        max_age=86400,
    )

    if settings.allowed_hosts_list != ["*"]:
        from starlette.middleware.trustedhost import TrustedHostMiddleware

        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)

    # ── Routers ───────────────────────────────────────────────────────────────
    for router in ALL_ROUTERS:
        app.include_router(router)

    # ── Friendly page redirects (/youtube -> /pages/youtube.html) ─────────────
    def _register_page_routes() -> None:
        for route_key, page in {**PLATFORM_PAGES, **EXTRA_PAGES}.items():
            def _make(target: str):
                async def _redirect() -> RedirectResponse:
                    return RedirectResponse(url=f"/pages/{target}", status_code=307)

                return _redirect

            app.get(f"/{route_key}", include_in_schema=False, name=f"page_{route_key}")(
                _make(page)
            )

        @app.get("/downloader", include_in_schema=False)
        async def to_downloader() -> RedirectResponse:
            return RedirectResponse(url="/#downloader-section", status_code=307)

    _register_page_routes()

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "error": f"http_{exc.status_code}",
                    "message": str(exc.detail),
                },
                headers=getattr(exc, "headers", None),
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "validation_error",
                "message": "The request body or query parameters are invalid.",
                "details": exc.errors()[:5],
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "server_error",
                "message": "An unexpected server error occurred.",
            },
        )

    # ── Static frontend (mounted LAST so /api/* always wins) ──────────────────
    if FRONTEND_DIR.exists():
        static_dir = FRONTEND_DIR / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        pages_dir = FRONTEND_DIR / "pages"
        if pages_dir.exists():
            app.mount("/pages", StaticFiles(directory=str(pages_dir), html=True), name="pages")

        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    else:  # pragma: no cover - only if the frontend folder is missing

        @app.get("/", include_in_schema=False)
        async def frontend_missing():
            return JSONResponse(
                status_code=200,
                content={
                    "app": settings.APP_NAME,
                    "version": settings.APP_VERSION,
                    "message": "Frontend folder not found, but the API is running.",
                    "docs": "/api/docs",
                    "platforms": sorted(PLATFORM_PAGES),
                },
            )

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=not settings.is_production,
    )