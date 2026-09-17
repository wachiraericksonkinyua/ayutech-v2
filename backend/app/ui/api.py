# app/ui/api.py
"""Thin httpx wrapper that automatically attaches the logged-in user's
Supabase access token as an ``Authorization: Bearer`` header."""

import httpx

import app.ui.state as app_state
from app.ui.state import API_BASE_URL


def auth_headers() -> dict:
    token = getattr(app_state, "access_token", "") or ""
    return {"Authorization": f"Bearer {token}"} if token else {}


def admin_headers() -> dict:
    token = getattr(app_state, "admin_token", "") or ""
    return {"Authorization": f"Bearer {token}"} if token else {}


def get(path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 8)
    headers = {**auth_headers(), **(kwargs.pop("headers", {}) or {})}
    return httpx.get(f"{API_BASE_URL}{path}", headers=headers, **kwargs)


def post(path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 10)
    headers = {**auth_headers(), **(kwargs.pop("headers", {}) or {})}
    return httpx.post(f"{API_BASE_URL}{path}", headers=headers, **kwargs)


def patch(path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 10)
    headers = {**auth_headers(), **(kwargs.pop("headers", {}) or {})}
    return httpx.patch(f"{API_BASE_URL}{path}", headers=headers, **kwargs)


def admin_get(path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 8)
    headers = {**admin_headers(), **(kwargs.pop("headers", {}) or {})}
    return httpx.get(f"{API_BASE_URL}{path}", headers=headers, **kwargs)


def admin_post(path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 45)  # long for Render cold boot on first login
    headers = {**admin_headers(), **(kwargs.pop("headers", {}) or {})}
    return httpx.post(f"{API_BASE_URL}{path}", headers=headers, **kwargs)


def admin_patch(path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 10)
    headers = {**admin_headers(), **(kwargs.pop("headers", {}) or {})}
    return httpx.patch(f"{API_BASE_URL}{path}", headers=headers, **kwargs)
