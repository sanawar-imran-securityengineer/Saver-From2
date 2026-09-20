"""API smoke tests for the unified SaverFrom backend.

Run from the repository root:
    backend/.venv/Scripts/python -m pytest backend/tests -v

These tests do NOT hit the network, so they are fast and deterministic.
Network behaviour is covered by ``test_live_extraction.py`` (opt-in).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app  # noqa: E402
from backend.routers import PLATFORM_PAGES  # noqa: E402
from backend.utils.platforms import platform_keys  # noqa: E402

EXPECTED_PLATFORMS = [
    "youtube",
    "tiktok",
    "instagram",
    "twitter",
    "reddit",
    "pinterest",
    "snapchat",
    "twitch",
    "threads",
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


# ── Registry ────────────────────────────────────────────────────────────────
def test_registry_contains_required_platforms():
    registered = set(platform_keys())
    for key in EXPECTED_PLATFORMS:
        assert key in registered, f"{key} missing from the platform registry"
    # Facebook is an extra platform carried over from the original project.
    assert "facebook" in registered


def test_every_platform_has_a_frontend_page():
    for key in platform_keys():
        assert key in PLATFORM_PAGES, f"{key} has no frontend page mapping"


def test_platform_page_files_exist():
    for page in PLATFORM_PAGES.values():
        assert (PROJECT_ROOT / "frontend" / "pages" / page).exists(), f"{page} is missing"


# ── Health ──────────────────────────────────────────────────────────────────
def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["platform_count"] == len(platform_keys())
    for key in platform_keys():
        assert key in body["platforms"]


def test_health_v1_alias_matches(client: TestClient):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_stats(client: TestClient):
    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert "cache" in body
    assert "circuit_breakers" in body


# ── Registry endpoint ───────────────────────────────────────────────────────
def test_platforms_endpoint(client: TestClient):
    body = client.get("/api/v1/platforms").json()
    assert body["success"] is True
    keys = {item["key"] for item in body["platforms"]}
    assert keys == set(platform_keys())
    # The frontend needs these fields for every card.
    for item in body["platforms"]:
        assert item["route"] == f"/{item['key']}"
        assert item["icon"].startswith("/static/icons/")
        assert item["accent_color"].startswith("#")
        assert item["formats"]


def test_platforms_endpoint_alias(client: TestClient):
    assert client.get("/api/platforms").json()["count"] == len(platform_keys())


# ── Detection ───────────────────────────────────────────────────────────────
DETECT_CASES = [
    ("youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("youtube", "https://youtu.be/dQw4w9WgXcQ"),
    ("tiktok", "https://www.tiktok.com/@user/video/7106594312292453675"),
    ("instagram", "https://www.instagram.com/reel/CtjoC2BNsB2/"),
    ("twitter", "https://x.com/user/status/1234567890123456789"),
    ("reddit", "https://www.reddit.com/r/aww/comments/abc123/title/"),
    ("pinterest", "https://www.pinterest.com/pin/1234567890/"),
    ("snapchat", "https://www.snapchat.com/spotlight/abcdef"),
    ("twitch", "https://www.twitch.tv/videos/1234567890"),
    ("threads", "https://www.threads.net/@user/post/abcdef"),
    ("facebook", "https://www.facebook.com/watch/?v=10153231379946729"),
]


@pytest.mark.parametrize("expected,url", DETECT_CASES)
def test_detect_url(client: TestClient, expected: str, url: str):
    response = client.post("/api/v1/detect", json={"url": url})
    assert response.status_code == 200
    body = response.json()
    assert body.get("success") is True, body
    assert body["platform"] == expected
    assert body["page"] == f"/pages/{PLATFORM_PAGES[expected]}"


def test_detect_rejects_unsupported_url(client: TestClient):
    body = client.post("/api/v1/detect", json={"url": "https://example.com/video/1"}).json()
    assert body["success"] is False
    assert body["error"] == "detect_error"


def test_detect_rejects_empty_url(client: TestClient):
    body = client.post("/api/v1/detect", json={"url": "   "}).json()
    assert body["success"] is False
    assert body["error"] == "empty_url"


# ── Validation ──────────────────────────────────────────────────────────────
def test_download_rejects_localhost(client: TestClient):
    body = client.post(
        "/api/v1/download", json={"url": "http://127.0.0.1/secret", "format": "best"}
    ).json()
    assert body["success"] is False
    assert body["error"] in ("validation_error", "detect_error")


def test_download_endpoint_is_reachable(client: TestClient):
    """A supported URL must reach the resolver (no 404/405/422)."""
    response = client.post(
        "/api/v1/download",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "720p"},
    )
    assert response.status_code == 200
    body = response.json()
    # Either real data or a clean error object — never a crash.
    assert "success" in body


# ── Per-platform routers ────────────────────────────────────────────────────
@pytest.mark.parametrize("key", platform_keys())
def test_platform_health(client: TestClient, key: str):
    response = client.get(f"/api/{key}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["platform"] == key
    assert body["server_side_download"] is True


@pytest.mark.parametrize("key", platform_keys())
def test_platform_formats(client: TestClient, key: str):
    response = client.get(f"/api/{key}/formats")
    assert response.status_code == 200
    body = response.json()
    assert body["formats"]
    assert body["options"]
    assert body["page"] == f"/pages/{PLATFORM_PAGES[key]}"


@pytest.mark.parametrize("key", platform_keys())
def test_platform_rejects_foreign_url(client: TestClient, key: str):
    """Each router must refuse a URL that belongs to a different platform."""
    foreign = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    if key == "youtube":
        pytest.skip("youtube is the reference URL")
    response = client.post(f"/api/{key}/resolve", json={"url": foreign, "option": "best"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "validation_error"


# ── Frontend routing ────────────────────────────────────────────────────────
@pytest.mark.parametrize("key", list(PLATFORM_PAGES))
def test_frontend_route_redirects_to_page(client: TestClient, key: str):
    """`/youtube` etc. must redirect to the matching page in /pages."""
    response = client.get(f"/{key}", follow_redirects=False)
    assert response.status_code in (307, 308)
    assert response.headers["location"] == f"/pages/{PLATFORM_PAGES[key]}"


def test_frontend_pages_are_served(client: TestClient):
    for page in PLATFORM_PAGES.values():
        response = client.get(f"/pages/{page}")
        assert response.status_code == 200, f"/pages/{page} not served"
        assert "text/html" in response.headers["content-type"]


def test_index_page_is_served(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_static_assets_are_served(client: TestClient):
    response = client.get("/static/icons/youtube.svg")
    assert response.status_code == 200


# ── File serving safety ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "filename",
    [
        "../requirements.txt",
        "..%2Frequirements.txt",
        "/etc/passwd",
        "normal_name.mp4",
        "00000000-0000-0000-0000-000000000000.exe",
    ],
)
def test_file_endpoint_rejects_unsafe_names(client: TestClient, filename: str):
    response = client.get(f"/api/file/{filename}")
    assert response.status_code in (404, 400, 422), f"{filename} should not be servable"


def test_file_endpoint_404_for_unknown_uuid(client: TestClient):
    response = client.get("/api/file/11111111-2222-3333-4444-555555555555.mp4")
    assert response.status_code == 404


# ─ Admin ───────────────────────────────────────────────────────────────────
def test_maintenance_toggle(client: TestClient):
    # Turn youtube into maintenance mode.
    body = client.post(
        "/api/v1/admin/maintenance",
        json={"platform": "youtube", "enabled": True, "reason": "test"},
    ).json()
    assert body["success"] is True
    assert body["state"] == "OPEN"

    # The unified endpoint must now refuse youtube requests.
    blocked = client.post(
        "/api/v1/download",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "720p"},
    ).json()
    assert blocked["success"] is False
    assert blocked["error"] == "maintenance"

    # Restore.
    restored = client.post(
        "/api/v1/admin/maintenance", json={"platform": "youtube", "enabled": False}
    ).json()
    assert restored["state"] == "CLOSED"


def test_maintenance_rejects_unknown_platform(client: TestClient):
    response = client.post(
        "/api/v1/admin/maintenance", json={"platform": "myspace", "enabled": True}
    )
    assert response.status_code == 400


def test_admin_settings_never_leaks_secrets(client: TestClient):
    body = client.get("/api/v1/admin/settings").json()
    assert "REDIS_URL" not in body
    assert "redis_url" not in body
    assert body["redis_configured"] in (True, False)