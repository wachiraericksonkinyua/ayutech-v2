"""Web entry point for the standalone AyuTech POS and admin dashboard."""

import flet.fastapi as flet_fastapi

from app.dashboard import main as dashboard_main

app = flet_fastapi.app(
    dashboard_main,
    app_name="AyuTech POS & Admin",
    app_short_name="AyuTech Admin",
    app_description="Staff POS and store management dashboard.",
)
