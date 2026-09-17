# app/core/auth_deps.py
"""Reusable FastAPI dependencies for verifying Supabase-issued sessions.

Every protected endpoint requires a valid ``Authorization: Bearer <token>``
header. The token is the Supabase access token returned by /auth/login.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.supabase_client import supabase
from app.core.security import decode_admin_token

# auto_error=False lets us raise a clean 401 instead of FastAPI's default 403
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_user(user_obj):
    """Normalise a supabase User object / dict into {id, email}."""
    if user_obj is None:
        return None
    user_id = user_obj.id if hasattr(user_obj, "id") else user_obj.get("id")
    email = user_obj.email if hasattr(user_obj, "email") else user_obj.get("email")
    if not user_id:
        return None
    return {"id": str(user_id), "email": email}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Validate the Bearer token against Supabase and return the caller."""
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    token = credentials.credentials
    try:
        res = supabase.auth.get_user(token)
        user_obj = getattr(res, "user", None) or (
            res.get("user") if isinstance(res, dict) else None
        )
    except Exception:
        raise _UNAUTHORIZED

    user = _extract_user(user_obj)
    if user is None:
        raise _UNAUTHORIZED
    return user


def require_owner(user_id: str, current_user: dict = Depends(get_current_user)):
    """Ensure the authenticated user only touches their own record."""
    if str(current_user.get("id")) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own account.",
        )
    return current_user


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Validate a staff/POS admin token (issued by /admin/auth/pin-login)."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_admin_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired staff session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "id": payload.get("sub"),
        "name": payload.get("name"),
        "role": payload.get("role", "staff"),
    }
