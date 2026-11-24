"""Web entry point for the standalone AyuTech POS and admin dashboard."""

import os
import secrets
from pathlib import Path

import flet.fastapi as flet_fastapi

from app.dashboard import main as dashboard_main

UPLOAD_DIR = os.getenv("FLET_UPLOAD_DIR", "/tmp/ayutech-admin-uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

app = flet_fastapi.app(
    dashboard_main,
    app_name="AyuTech POS & Admin",
    app_short_name="AyuTech Admin",
    app_description="Staff POS and store management dashboard.",
    upload_dir=UPLOAD_DIR,
    max_upload_size=5 * 1024 * 1024,
    secret_key=os.getenv("FLET_SECRET_KEY") or secrets.token_urlsafe(32),
)
