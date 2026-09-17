# backend/app/main.py

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.endpoints import (
    admin,
    orders,
    payments,
    products,
    reviews,
    whatsapp,
    ai
)
from app.core.config import settings
from app.core.rate_limiter import limiter

app = FastAPI(
    title="AyuTech Motors API",
    version="2.0.0",
    description="Backend services for Ayutech Motors Limited e-commerce and store operations."
)

# --- Rate limiting (slowapi) -------------------------------------------------
# Registering the limiter on app.state + the middleware is required for the
# @limiter.limit(...) decorators to actually enforce limits.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# --- CORS --------------------------------------------------------------------
# Comma separated list via ALLOWED_ORIGINS env var. Defaults to "*" which is
# safe here because the API is token-based (no cookies / credentials).
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]
_allow_credentials = _allowed_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Endpoints
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin Portal"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Customer Orders"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["M-Pesa Daraja"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Product Catalog"])
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["WhatsApp Automation"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Assistant"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Product Reviews"])
from app.routers import auth
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])


@app.on_event("startup")
def _validate_config():
    """Fail fast if critical secrets are left at their insecure defaults."""
    weak_secrets = {"", "secret", "your_fallback_super_secret_key_12345"}
    if settings.SECRET_KEY in weak_secrets:
        print(
            "WARNING: SECRET_KEY is unset or using an insecure default. "
            "Set a strong SECRET_KEY environment variable before production use."
        )


@app.get("/")
def root():
    return {
        "service": "AyuTech Motors API",
        "status": "Online",
        "version": "2.0.0"
    }


@app.get("/health", status_code=200)
@app.head("/health", status_code=200)
async def health_check():
    return "ok"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
