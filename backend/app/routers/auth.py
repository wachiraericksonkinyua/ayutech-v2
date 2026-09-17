import os
import secrets
import time
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from app.db.supabase_client import supabase
from app.core.rate_limiter import limiter
from app.core.auth_deps import get_current_user, require_owner
import uuid

router = APIRouter(prefix="/auth", tags=["Auth"])

# Upload guards
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


class AuthPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class ForgotPasswordPayload(BaseModel):
    email: EmailStr
    redirect_to: str = ""


class OAuthUrlPayload(BaseModel):
    provider: str = "google"
    redirect_to: str = ""


class OneTimeTokenPayload(BaseModel):
    token: str


class ResetExchangePayload(BaseModel):
    code: str = ""
    access_token: str = ""
    refresh_token: str = ""
    type: str = ""
    error: str = ""
    error_description: str = ""


class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class OAuthExchangePayload(BaseModel):
    code: str
    code_verifier: str = ""
    redirect_to: str = ""


SUPPORTED_OAUTH_PROVIDERS = {"google", "apple", "facebook", "github"}

# ---------------------------------------------------------------------------
# One-time tokens
# ---------------------------------------------------------------------------
# The OAuth / password-recovery redirects come back to the backend (or are
# consumed by it), so we never hand raw provider codes or session tokens to the
# browser address bar. Instead we stash the resulting session under an opaque,
# short-lived, single-use token that the client exchanges for a real session.
_TOKEN_TTL_SECONDS = 300
_ONE_TIME_TOKENS: dict = {}


def _purge_tokens() -> None:
    now = time.time()
    for key in list(_ONE_TIME_TOKENS.keys()):
        if now - _ONE_TIME_TOKENS[key].get("created_at", 0) > _TOKEN_TTL_SECONDS:
            _ONE_TIME_TOKENS.pop(key, None)


def _store_token(kind: str, data: dict) -> str:
    _purge_tokens()
    token = secrets.token_urlsafe(32)
    _ONE_TIME_TOKENS[token] = {"kind": kind, "created_at": time.time(), **data}
    return token


def _take_token(token: str, kind: str):
    _purge_tokens()
    entry = _ONE_TIME_TOKENS.get(token)
    if not entry or entry.get("kind") != kind:
        return None
    return entry


def _public_base_url(request: Request) -> str:
    """Best-effort public origin for building callback URLs.

    Render injects RENDER_EXTERNAL_URL; PUBLIC_BASE_URL can be set manually on
    other hosts. Falls back to the incoming request's base URL.
    """
    for env_name in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        value = (os.getenv(env_name, "") or "").strip()
        if value:
            return value.rstrip("/")
    return str(request.base_url).rstrip("/")


def _client_app_url() -> str:
    """Absolute or relative URL of the Flet customer app (defaults to /shop)."""
    base = (os.getenv("WEB_APP_URL", "") or "").strip()
    if not base:
        base = "/shop"
    if not base.endswith("/"):
        base += "/"
    return base


def _redirect_to_client(params: dict) -> RedirectResponse:
    query = urlencode({k: v for k, v in params.items() if v})
    return RedirectResponse(f"{_client_app_url()}?{query}")


_RESET_CALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AyuTech &middot; Securing your reset link</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               background: #F6F4F1; color: #1B1714; display: grid; place-items: center;
               min-height: 100vh; margin: 0; text-align: center; padding: 24px; }
        .card { background: #fff; border: 1px solid #E8E4DE; border-radius: 18px;
                padding: 32px; max-width: 360px; box-shadow: 0 12px 30px rgba(0,0,0,.06); }
        .dot { width: 46px; height: 46px; border-radius: 50%; margin: 0 auto 16px;
               background: linear-gradient(180deg,#E8444F,#B11728); color: #fff;
               display: grid; place-items: center; font-weight: 800; font-size: 22px; }
        h1 { font-size: 18px; margin: 0 0 8px; }
        p { color: #6D665E; font-size: 14px; margin: 0; }
    </style>
</head>
<body>
    <div class="card">
        <div class="dot">A</div>
        <h1>Securing your reset link</h1>
        <p id="status">Please wait while we verify your link&hellip;</p>
    </div>
    <script>
    (function () {
        var search = new URLSearchParams(window.location.search);
        var hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
        var payload = {
            code: search.get('code') || '',
            access_token: hash.get('access_token') || search.get('access_token') || '',
            refresh_token: hash.get('refresh_token') || search.get('refresh_token') || '',
            type: hash.get('type') || search.get('type') || '',
            error: hash.get('error') || search.get('error') || '',
            error_description: hash.get('error_description') || search.get('error_description') || ''
        };
        var appUrl = '__APP_URL__';
        var statusEl = document.getElementById('status');
        fetch('__API_URL__/auth/reset-exchange', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (r) { return r.json().catch(function () { return {}; }); })
          .then(function (data) {
            if (data && data.reset_token) {
                window.location.replace(appUrl + '?reset_token=' + encodeURIComponent(data.reset_token));
            } else {
                var msg = (data && (data.detail || data.error_description)) || 'This reset link is invalid or has expired.';
                statusEl.textContent = msg;
                window.location.replace(appUrl + '?oauth_error=' + encodeURIComponent(msg));
            }
        }).catch(function () {
            statusEl.textContent = 'Could not reach the server. Redirecting&hellip;';
            window.location.replace(appUrl + '?oauth_error=' + encodeURIComponent('Could not complete password reset.'));
        });
    })();
    </script>
</body>
</html>"""


def _normalise_auth_user(user_obj, session):
    """Pull (user_id, email, access_token, refresh_token) from an AuthResponse."""
    user_id = user_obj.id if hasattr(user_obj, "id") else (user_obj or {}).get("id")
    email = user_obj.email if hasattr(user_obj, "email") else (user_obj or {}).get("email")
    access_token = ""
    refresh_token = ""
    if session is not None:
        access_token = (
            session.access_token if hasattr(session, "access_token")
            else (session or {}).get("access_token", "")
        )
        refresh_token = (
            session.refresh_token if hasattr(session, "refresh_token")
            else (session or {}).get("refresh_token", "")
        )
    return str(user_id or ""), email, access_token or "", refresh_token or ""


class ProfileUpdate(BaseModel):
    username: str = Field(default="", max_length=50)
    full_name: str = Field(default="", max_length=120)
    birth_date: str = Field(default="", max_length=20)
    gender: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=20)
    avatar_url: str = Field(default="", max_length=500)
    banner_url: str = Field(default="", max_length=500)
    addresses: list = Field(default_factory=list)


@router.post("/register")
@limiter.limit("5/minute")
def register_user(request: Request, payload: AuthPayload):
    try:
        res = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password
        })
        return {"message": "Account created successfully! Please check your email for verification.", "user": res.user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
@limiter.limit("10/minute")
def login_user(request: Request, payload: AuthPayload):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        if res.session is None:
            raise HTTPException(status_code=401, detail="Login failed: no active session returned.")

        return {
            "message": "Login successful",
            "access_token": res.session.access_token,
            "user": res.user
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid email or password.")


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(request: Request, payload: ForgotPasswordPayload):
    """Send a password reset link. Always returns success (no email enumeration).

    Supabase's native recovery flow: the emailed link comes back to
    /auth/reset-callback, which safely forwards the user into the app's reset
    view via an opaque one-time token.
    """
    redirect_to = (payload.redirect_to or "").strip() or (
        _public_base_url(request) + "/api/v1/auth/reset-callback"
    )
    try:
        supabase.auth.reset_password_for_email(
            payload.email, {"redirect_to": redirect_to}
        )
    except Exception as e:
        print(f"Password reset warning: {e}")
    return {
        "status": "success",
        "message": "If that email is registered, a reset link has been sent.",
    }


@router.get("/reset-callback", response_class=HTMLResponse)
def reset_callback():
    """Landing page for the Supabase recovery link.

    The recovery link may carry the credentials either in the query string
    (PKCE ``code``) or in the URL fragment (implicit ``access_token``). The
    fragment never reaches the server, so a tiny script forwards everything to
    /auth/reset-exchange and then hands the app an opaque reset token.
    """
    app_url = _client_app_url()
    api_url = _public_base_url_for_page()
    html = (
        _RESET_CALLBACK_HTML
        .replace("__APP_URL__", app_url)
        .replace("__API_URL__", api_url)
    )
    return HTMLResponse(content=html)


def _public_base_url_for_page() -> str:
    """Absolute API base used by the reset-callback script (no request object)."""
    for env_name in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        value = (os.getenv(env_name, "") or "").strip()
        if value:
            return value.rstrip("/") + "/api/v1"
    return "/api/v1"


@router.post("/reset-exchange")
@limiter.limit("20/minute")
def reset_exchange(request: Request, payload: ResetExchangePayload):
    """Validate the recovery credentials and return a short-lived reset token."""
    if payload.error:
        raise HTTPException(status_code=400, detail=payload.error)

    access_token = ""
    refresh_token = ""
    if payload.code:
        try:
            res = supabase.auth.exchange_code_for_session({"auth_code": payload.code})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Reset link is invalid or expired: {e}")
        user_obj = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)
        session = getattr(res, "session", None) or (res.get("session") if isinstance(res, dict) else None)
        _, _, access_token, refresh_token = _normalise_auth_user(user_obj, session)
    elif payload.access_token and payload.refresh_token:
        access_token = payload.access_token
        refresh_token = payload.refresh_token
    else:
        raise HTTPException(status_code=400, detail="Reset link is missing its token.")

    if not access_token or not refresh_token:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")

    token = _store_token(
        "reset", {"access_token": access_token, "refresh_token": refresh_token}
    )
    return {"status": "success", "reset_token": token}


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(request: Request, payload: ResetPasswordPayload):
    """Set a new password using a valid one-time reset token."""
    entry = _take_token(payload.token, "reset")
    if not entry:
        raise HTTPException(
            status_code=400,
            detail="This reset link has expired. Please request a new one.",
        )
    try:
        supabase.auth.set_session(entry["access_token"], entry["refresh_token"])
        supabase.auth.update_user({"password": payload.new_password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not update password: {e}")
    finally:
        _ONE_TIME_TOKENS.pop(payload.token, None)
        # Keep the shared server-side client clean; never hold a user session.
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    return {"status": "success", "message": "Password updated. You can now sign in."}


def _mirror_customer(user_id: str, email: str) -> None:
    """Mirror an OAuth/Google user into the customers table so profile/orders work."""
    try:
        supabase.table("customers").upsert({
            "id": str(user_id),
            "email": email,
        }).execute()
    except Exception as db_err:
        print(f"OAuth customer mirror warning: {db_err}")


@router.post("/oauth-url")
def oauth_url(request: Request, payload: OAuthUrlPayload):
    """Return the provider sign-in URL plus the PKCE verifier for the callback.

    When the client does not supply a ``redirect_to`` (the web app), we point
    Supabase at our own callback endpoint so the browser is never stranded on
    the API landing page. Desktop clients keep using their localhost listener.
    """
    provider = (payload.provider or "google").lower()
    if provider not in SUPPORTED_OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported sign-in provider.")

    redirect_to = (payload.redirect_to or "").strip() or (
        _public_base_url(request) + "/api/v1/auth/oauth-callback"
    )
    options = {"redirect_to": redirect_to}
    try:
        res = supabase.auth.sign_in_with_oauth({"provider": provider, "options": options})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not start sign-in: {e}")

    verifier = ""
    try:
        verifier = supabase.auth._storage.get_item(
            f"{supabase.auth._storage_key}-code-verifier"
        ) or ""
    except Exception:
        verifier = ""
    return {
        "status": "success",
        "url": res.url,
        "code_verifier": verifier,
        "redirect_to": redirect_to,
    }


@router.get("/oauth-callback")
def oauth_callback(request: Request):
    """Handle the Google/OAuth redirect, then send the browser back into the app.

    The code is exchanged server-side (the PKCE verifier never leaves the
    backend) and the resulting session is hidden behind an opaque one-time
    token that the client consumes from the URL.
    """
    error = request.query_params.get("error")
    error_desc = request.query_params.get("error_description") or error
    code = request.query_params.get("code")
    if error or not code:
        return _redirect_to_client(
            {"oauth_error": error_desc or "Google sign-in was cancelled."}
        )

    try:
        res = supabase.auth.exchange_code_for_session({"auth_code": code})
    except Exception as e:
        return _redirect_to_client({"oauth_error": f"Google sign-in failed: {e}"})

    user_obj = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)
    session = getattr(res, "session", None) or (res.get("session") if isinstance(res, dict) else None)
    if user_obj is None:
        return _redirect_to_client({"oauth_error": "Google sign-in failed: no user returned."})

    user_id, email, access_token, _refresh = _normalise_auth_user(user_obj, session)
    _mirror_customer(user_id, email)

    login_token = _store_token(
        "login",
        {"access_token": access_token, "user": {"id": user_id, "email": email}},
    )
    return _redirect_to_client({"login_token": login_token})


@router.post("/oauth-exchange")
def oauth_exchange(payload: OAuthExchangePayload):
    """Exchange the OAuth callback code for a session (desktop flow)."""
    params = {"auth_code": payload.code}
    if payload.code_verifier:
        params["code_verifier"] = payload.code_verifier
    if payload.redirect_to:
        params["redirect_to"] = payload.redirect_to
    try:
        res = supabase.auth.exchange_code_for_session(params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sign-in failed: {e}")

    user_obj = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)
    session = getattr(res, "session", None) or (res.get("session") if isinstance(res, dict) else None)
    if user_obj is None:
        raise HTTPException(status_code=400, detail="Sign-in failed: no user returned.")

    user_id, email, access_token, _refresh = _normalise_auth_user(user_obj, session)
    _mirror_customer(user_id, email)

    return {
        "status": "success",
        "access_token": access_token,
        "user": {"id": str(user_id), "email": email},
    }


@router.post("/consume-login-token")
@limiter.limit("30/minute")
def consume_login_token(request: Request, payload: OneTimeTokenPayload):
    """Redeem a one-time login token produced by /oauth-callback."""
    entry = _take_token(payload.token, "login")
    if not entry:
        raise HTTPException(
            status_code=400,
            detail="This sign-in link has expired. Please sign in again.",
        )
    _ONE_TIME_TOKENS.pop(payload.token, None)
    return {
        "status": "success",
        "access_token": entry.get("access_token", ""),
        "user": entry.get("user", {}),
    }


@router.get("/profile")
def get_customer_profile(email: str, current_user: dict = Depends(get_current_user)):
    """Fetch the caller's own profile by email."""
    if str(current_user.get("email", "")).lower() != email.strip().lower():
        raise HTTPException(status_code=403, detail="You can only access your own account.")
    try:
        res = supabase.table("customers").select("*").eq("email", email).single()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Customer profile not found.")


@router.get("/profile/{user_id}")
def get_customer_profile_by_id(user_id: str, current_user: dict = Depends(require_owner)):
    try:
        res = supabase.table("customers").select("*").eq("id", user_id).single()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Customer profile not found.")


def _normalise_birth_date(value) -> str:
    """Return an ISO ``YYYY-MM-DD`` date or ``""`` for the DATE column.

    The UI field is free text, so accept a few common formats and drop anything
    unparseable instead of letting Postgres reject the whole profile update.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


@router.patch("/profile/{user_id}")
def update_customer_profile(
    user_id: str,
    payload: ProfileUpdate,
    current_user: dict = Depends(require_owner),
):
    try:
        data = payload.model_dump()
        data["birth_date"] = _normalise_birth_date(data.get("birth_date"))
        update_data = {
            k: v for k, v in data.items()
            if v not in [None, ""] or k == "addresses"
        }
        if not update_data:
            raise HTTPException(status_code=400, detail="Nothing to update.")

        # Upsert so a mirrored customer row is created if it doesn't exist yet
        res = supabase.table("customers").upsert({
            "id": user_id,
            **update_data,
        }, on_conflict="id").execute()

        updated = getattr(res, "data", None) or []
        return {"status": "success", "profile": updated[0] if updated else update_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update profile: {str(e)}")


@router.post("/upload-image/", status_code=201)
async def upload_profile_image(
    request: Request,
    type: str = Query("avatar", pattern="^(avatar|banner)$"),
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        # Validate declared content type
        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF images are allowed.")

        # Validate extension
        file_extension = (image.filename or "image.jpg").split(".")[-1].lower()
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported image file extension.")

        contents = await image.read()

        # Validate size
        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image is too large. Maximum size is 5 MB.")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Validate magic bytes so a renamed script can't be stored as an image
        if not _looks_like_image(contents):
            raise HTTPException(status_code=400, detail="File does not appear to be a valid image.")

        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        folder = "avatars" if type == "avatar" else "banners"
        file_path = f"{folder}/{unique_filename}"

        def _try_upload(bucket: str):
            supabase.storage.from_(bucket).upload(
                path=file_path,
                file=contents,
                file_options={"content-type": content_type or "image/jpeg"}
            )
            return supabase.storage.from_(bucket).get_public_url(file_path)

        try:
            image_url = _try_upload("profile-images")
        except Exception:
            # Bucket may not exist yet - try to create it automatically
            try:
                supabase.storage.create_bucket("profile-images", options={"public": True})
                image_url = _try_upload("profile-images")
            except Exception:
                # Last resort: reuse the existing product-images bucket so uploads still work
                image_url = _try_upload("product-images")
        return {"image_url": image_url, "type": type}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")


def _looks_like_image(data: bytes) -> bool:
    """Check common image magic numbers."""
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":            # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":       # PNG
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):     # GIF
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WEBP
        return True
    return False
