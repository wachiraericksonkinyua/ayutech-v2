import os
import secrets
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Never fall back to a guessable key. In production SECRET_KEY must be set.
# For local dev we generate a random per-process key (tokens won't survive restarts).
_INSECURE_DEFAULTS = {"", "secret", "your_fallback_super_secret_key_12345"}
SECRET_KEY = os.getenv("SECRET_KEY", "")
if SECRET_KEY in _INSECURE_DEFAULTS:
    SECRET_KEY = secrets.token_urlsafe(48)

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))

# Staff / POS admin tokens use their own secret (falls back to SECRET_KEY).
_ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "") or SECRET_KEY
ADMIN_TOKEN_EXPIRE_MINUTES = int(os.getenv("ADMIN_TOKEN_EXPIRE_MINUTES", 60 * 12))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored bcrypt hash safely."""
    # Truncate to 72 bytes to satisfy bcrypt limits
    safe_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(safe_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generates a secure bcrypt hash."""
    safe_password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(safe_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Creates signed JWT token with payload claims."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_admin_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Signs a staff/POS session token. ``typ`` marks it as an admin token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ADMIN_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "typ": "admin"})
    return jwt.encode(to_encode, _ADMIN_SECRET, algorithm=ALGORITHM)


def decode_admin_token(token: str) -> dict:
    """Verifies a staff/POS token and ensures it is an admin token."""
    payload = jwt.decode(token, _ADMIN_SECRET, algorithms=[ALGORITHM])
    if payload.get("typ") != "admin":
        raise jwt.InvalidTokenError("Not an admin token")
    return payload
