"""Hostinger Passenger entry point.

hPanel -> Advanced -> Setup Python App
  Application root         : this repository folder
  Application startup file : passenger_wsgi.py
  Application entry point  : application
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

downloads = PROJECT_ROOT / "backend" / "downloads"
downloads.mkdir(parents=True, exist_ok=True)

from a2wsgi import ASGIMiddleware  # noqa: E402

from backend.main import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
