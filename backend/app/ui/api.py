# app/ui/api.py
"""Thin httpx wrapper that automatically attaches the logged-in user's
Supabase access token as an ``Authorization: Bearer`` header."""

import json
import httpx

import app.ui.state as app_state
from app.ui.state import API_BASE_URL


def extract_clean_error_message(raw, fallback: str) -> str:
    """Extract a short human-readable message without exposing serialized JSON."""
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return fallback
        if value.startswith(("{", "[")):
            try:
                return extract_clean_error_message(json.loads(value), fallback)
            except (TypeError, ValueError):
                return fallback
        return value if len(value) <= 240 else fallback

    if isinstance(raw, dict):
        for key in ("detail", "message", "error"):
            if key in raw:
                message = extract_clean_error_message(raw[key], fallback)
                if message != fallback:
                    return message
    elif isinstance(raw, list):
        for item in raw:
            message = extract_clean_error_message(item, fallback)
            if message != fallback:
                return message
    return fallback


def user_facing_error(response: httpx.Response, fallback: str = "") -> str:
    """Map API failures to readable copy, using safe server details when appropriate."""
    status_fallbacks = {
        401: "Please sign in again and retry.",
        403: "You don't have permission to do that.",
        404: fallback or "We couldn't find what you were looking for.",
        429: "Please wait a moment and try again.",
    }
    if response.status_code >= 500:
        return fallback or "Something went wrong. Please try again shortly."

    default = status_fallbacks.get(
        response.status_code,
        fallback or "We couldn't complete that request. Please try again.",
    )
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        payload = response.text
    return extract_clean_error_message(payload, default)


def sanitize_chat_reply(value) -> str:
    """Prevent accidentally rendering provider error objects in customer chat."""
    fallback = "I'm having trouble checking the catalog right now. Please try again or contact the shop."
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    if text.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            return fallback
        if isinstance(payload, dict) and isinstance(payload.get("reply"), str):
            return sanitize_chat_reply(payload["reply"])
        return fallback
    object_start = text.find("{")
    if object_start >= 0:
        try:
            payload, _ = json.JSONDecoder().raw_decode(text[object_start:])
        except (TypeError, ValueError):
            payload = None
        if isinstance(payload, dict) and ("error" in payload or "detail" in payload):
            return fallback
    if text.lower().startswith(("ai service error:", "provider error:")):
        return fallback
    return text if text and len(text) <= 1200 else fallback


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
