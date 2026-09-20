"""ASGI -> WSGI entry point for Hostinger shared / cloud hosting.

Hostinger's "Setup Python App" wizard (LiteSpeed + Passenger) starts Python
applications through a WSGI callable, but this project is a **FastAPI (ASGI)**
application. ``a2wsgi`` bridges the two so the exact same app runs unchanged
on shared hosting.

How Hostinger uses this file
----------------------------
1. hPanel -> Advanced -> "Setup Python App"
2. Application root      : the folder that contains ``backend/``
3. Application startup file: ``deploy/hostinger/passenger_wsgi.py``
4. Application entry point : ``application``

On a **VPS** you do NOT need this file — run uvicorn directly instead (see
``deploy/hostinger/README.md``).

Note: Passenger buffers responses, so the streaming endpoints
(``/api/v1/proxy-download``) are best used on a VPS. The normal JSON endpoints
and the server-side download endpoints work everywhere.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Make the repository root importable ─────────────────────────────────────
# passenger_wsgi.py lives in <root>/deploy/hostinger/, so the project root is
# two levels up. We add it to sys.path before importing "backend".
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Hostinger's "Setup Python App" does not always set the working directory.
os.chdir(PROJECT_ROOT)

from a2wsgi import ASGIMiddleware  # noqa: E402

from backend.main import app as asgi_app  # noqa: E402

# Passenger looks for a module-level callable named "application".
application = ASGIMiddleware(asgi_app)