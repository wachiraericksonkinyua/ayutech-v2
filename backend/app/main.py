# backend/app/main.py

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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


_LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="AyuTech Motors Limited - genuine Japanese and heavy-duty automotive spares on Kirinyaga Road, Nairobi. Browse, order and pay via M-Pesa.">
    <meta name="theme-color" content="#0F0D0C">
    <title>AyuTech Motors Limited | Kirinyaga Road Spares</title>
    <style>
        :root {
            --bg: #0F0D0C;
            --surface: #181615;
            --surface-raised: #211E1C;
            --border: #2E2A27;
            --text: #F4F2EF;
            --body: #B6AEA4;
            --muted: #857D74;
            --accent: #EF4650;
            --accent-deep: #B11728;
            --success: #28CE7C;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }
        a { color: inherit; text-decoration: none; }
        .wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px; }

        header {
            position: sticky; top: 0; z-index: 20;
            backdrop-filter: blur(10px);
            background: rgba(15, 13, 12, 0.82);
            border-bottom: 1px solid var(--border);
        }
        .nav { display: flex; align-items: center; justify-content: space-between; height: 68px; }
        .brand { display: flex; align-items: center; gap: 12px; font-weight: 700; letter-spacing: .3px; }
        .logo {
            width: 40px; height: 40px; border-radius: 12px;
            display: grid; place-items: center; font-weight: 800; font-size: 20px; color: #fff;
            background: linear-gradient(180deg, #E8444F, #B11728);
            box-shadow: 0 8px 20px rgba(232, 68, 79, .35);
        }
        .nav-links { display: flex; gap: 22px; font-size: 14px; color: var(--body); }
        .nav-links a:hover { color: var(--text); }
        .nav-cta {
            padding: 9px 18px; border-radius: 10px; font-size: 14px; font-weight: 600; color: #fff;
            background: linear-gradient(180deg, #E8444F, #B11728);
        }

        .hero { padding: 84px 0 64px; text-align: center; }
        .badge {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 7px 14px; border-radius: 999px; font-size: 12.5px; color: var(--body);
            background: var(--surface-raised); border: 1px solid var(--border); margin-bottom: 22px;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px rgba(40, 206, 124, .15); }
        h1 { font-size: clamp(30px, 5.5vw, 54px); line-height: 1.1; letter-spacing: -1px; font-weight: 800; }
        h1 span { color: var(--accent); }
        .sub { max-width: 620px; margin: 20px auto 0; font-size: clamp(15px, 2vw, 18px); color: var(--body); }
        .cta-row { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 34px; }
        .btn {
            display: inline-flex; align-items: center; gap: 9px;
            padding: 14px 24px; border-radius: 12px; font-weight: 700; font-size: 15px;
            transition: transform .15s ease, background .2s ease, border-color .2s ease;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-primary { background: linear-gradient(180deg, #E8444F, #B11728); color: #fff; box-shadow: 0 12px 28px rgba(232, 68, 79, .32); }
        .btn-ghost { background: var(--surface-raised); border: 1px solid var(--border); color: var(--text); }
        .btn-ghost:hover { border-color: var(--accent); }
        .trust { margin-top: 26px; font-size: 13px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 18px; justify-content: center; }
        .trust b { color: var(--body); }

        section { padding: 64px 0; }
        .section-head { text-align: center; margin-bottom: 38px; }
        .section-head h2 { font-size: clamp(22px, 3.4vw, 32px); font-weight: 800; letter-spacing: -.4px; }
        .section-head p { color: var(--body); margin-top: 10px; font-size: 15px; }
        .eyebrow { color: var(--accent); font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.4px; margin-bottom: 10px; }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }
        .card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 24px;
            transition: border-color .2s ease, transform .2s ease;
        }
        .card:hover { border-color: #3f3936; transform: translateY(-3px); }
        .card .ico {
            width: 44px; height: 44px; border-radius: 13px; display: grid; place-items: center;
            font-size: 21px; margin-bottom: 14px; background: rgba(239, 70, 80, .12); border: 1px solid rgba(239, 70, 80, .25);
        }
        .card h3 { font-size: 16px; margin-bottom: 6px; }
        .card p { color: var(--body); font-size: 14px; }

        .downloads { background: linear-gradient(180deg, #151312, #0F0D0C); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
        .dl-card { display: flex; flex-direction: column; }
        .dl-card .tag { align-self: flex-start; font-size: 11px; font-weight: 700; letter-spacing: .6px; text-transform: uppercase; color: var(--accent); background: rgba(239, 70, 80, .12); padding: 4px 10px; border-radius: 999px; margin-bottom: 14px; }
        .dl-card .btn { margin-top: auto; justify-content: center; }
        .dl-card p { margin-bottom: 18px; }

        footer { padding: 54px 0 40px; border-top: 1px solid var(--border); color: var(--body); font-size: 14px; }
        .foot-grid { display: flex; flex-wrap: wrap; gap: 28px; justify-content: space-between; }
        .foot-brand { max-width: 320px; }
        .foot-brand p { margin-top: 12px; color: var(--muted); font-size: 13px; }
        .foot-col h4 { color: var(--text); font-size: 13px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
        .foot-col a { display: block; color: var(--body); padding: 4px 0; }
        .foot-col a:hover { color: var(--accent); }
        .copy { margin-top: 40px; padding-top: 22px; border-top: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; color: var(--muted); font-size: 12.5px; }
        @media (max-width: 640px) { .nav-links { display: none; } .hero { padding: 56px 0 40px; } }
    </style>
</head>
<body>
    <header>
        <div class="wrap nav">
            <div class="brand"><div class="logo">A</div> AyuTech Motors</div>
            <nav class="nav-links">
                <a href="#highlights">Why Us</a>
                <a href="#downloads">Get the App</a>
                <a href="/docs">API Docs</a>
            </nav>
            __WEB_NAV__
        </div>
    </header>

    <main>
        <section class="hero wrap">
            <div class="badge"><span class="dot"></span> Kirinyaga Road, Nairobi &middot; Open today</div>
            <h1>Genuine auto spares,<br><span>delivered to your garage.</span></h1>
            <p class="sub">Japanese and heavy-duty parts for Toyota, Mazda, Isuzu, Nissan and more. Find the right fitment with our AI assistant, pay via M-Pesa, and get it delivered.</p>
            <div class="cta-row">
                __WEB_HERO__
                __DL_HERO__
                <a href="__WHATSAPP_URL__" class="btn btn-ghost">Chat on WhatsApp</a>
            </div>
            <div class="trust">
                <span><b>100%</b> Genuine parts</span>
                <span><b>M-Pesa</b> checkout</span>
                <span><b>Same-day</b> Nairobi delivery</span>
            </div>
        </section>

        <section id="highlights">
            <div class="wrap">
                <div class="section-head">
                    <div class="eyebrow">Why AyuTech</div>
                    <h2>Everything your garage needs</h2>
                    <p>From engine and brake parts to suspension and heavy-duty spares.</p>
                </div>
                <div class="grid">
                    <div class="card">
                        <div class="ico">&#128295;</div>
                        <h3>Genuine Japanese Spares</h3>
                        <p>OEM and quality aftermarket parts for Toyota, Mazda, Nissan, Subaru and Mitsubishi.</p>
                    </div>
                    <div class="card">
                        <div class="ico">&#128666;</div>
                        <h3>Heavy-Duty &amp; Commercial</h3>
                        <p>Isuzu, Fuso, Hino and truck parts built to keep your fleet on the road.</p>
                    </div>
                    <div class="card">
                        <div class="ico">&#129302;</div>
                        <h3>AI Fitment Assistant</h3>
                        <p>Tell us your vehicle or engine code and we will match the exact part you need.</p>
                    </div>
                    <div class="card">
                        <div class="ico">&#128241;</div>
                        <h3>M-Pesa Payments</h3>
                        <p>Pay securely with M-Pesa STK push straight from the app. No cash hassle.</p>
                    </div>
                    <div class="card">
                        <div class="ico">&#128230;</div>
                        <h3>Fast Delivery</h3>
                        <p>Same-day dispatch within Nairobi and countrywide courier options.</p>
                    </div>
                    <div class="card">
                        <div class="ico">&#127978;</div>
                        <h3>Shop &amp; Web Access</h3>
                        <p>Visit us on Kirinyaga Road or shop online from anywhere in Kenya.</p>
                    </div>
                </div>
            </div>
        </section>

        <section id="downloads" class="downloads">
            <div class="wrap">
                <div class="section-head">
                    <div class="eyebrow">Get the App</div>
                    <h2>Shop AyuTech your way</h2>
                    <p>__DOWNLOADS_SUB__</p>
                </div>
                <div class="grid">
                    __WEB_DL_CARD__
                    <div class="card dl-card">
                        <span class="tag">Android</span>
                        <h3>Android APK</h3>
                        <p>Install the AyuTech app on your phone for notifications and one-tap reorders.</p>
                        <a href="__APK_URL__" class="btn btn-ghost">Download APK</a>
                    </div>
                    <div class="card dl-card">
                        <span class="tag">Desktop</span>
                        <h3>Windows &amp; Linux</h3>
                        <p>Run the full desktop client on your shop or office computer.</p>
                        <a href="__DESKTOP_URL__" class="btn btn-ghost">Download Desktop App</a>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <footer>
        <div class="wrap foot-grid">
            <div class="foot-brand">
                <div class="brand"><div class="logo">A</div> AyuTech Motors</div>
                <p>Your trusted plug for genuine automotive spares on Kirinyaga Road, Nairobi.</p>
            </div>
            <div class="foot-col">
                <h4>Shop</h4>
                __WEB_FOOT__
                <a href="__APK_URL__">Android APK</a>
                <a href="__DESKTOP_URL__">Desktop App</a>
            </div>
            <div class="foot-col">
                <h4>Developers</h4>
                <a href="/docs">API Documentation</a>
                <a href="/health">Service Health</a>
                <a href="__REPO_URL__">GitHub Repository</a>
            </div>
            <div class="foot-col">
                <h4>Contact</h4>
                <a href="__WHATSAPP_URL__">WhatsApp</a>
                <a href="__MAPS_URL__">Directions</a>
                <a href="mailto:support@ayutech.co.ke">support@ayutech.co.ke</a>
            </div>
        </div>
        <div class="wrap copy">
            <span>&copy; 2026 AyuTech Motors Limited. All rights reserved.</span>
            <span>Kirinyaga Road, Nairobi, Kenya</span>
        </div>
    </footer>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """Serve the public landing page.

    Clients that explicitly ask for JSON (e.g. monitoring tools) still get the
    original service metadata so nothing that depended on the old response breaks.
    """
    accept = (request.headers.get("accept") or "").lower()
    wants_json = "application/json" in accept and "text/html" not in accept
    if wants_json:
        return JSONResponse({
            "service": "AyuTech Motors API",
            "status": "Online",
            "version": "2.0.0",
        })

    repo = os.getenv("GITHUB_REPO_URL", "https://github.com/wachiraericksonkinyua/ayutech-v2")
    web_app = (os.getenv("WEB_APP_URL", "") or "").strip()
    apk_url = os.getenv("APK_DOWNLOAD_URL", f"{repo}/releases/latest/download/ayutech.apk")
    releases_url = f"{repo}/releases/latest"
    desktop_url = os.getenv("DESKTOP_DOWNLOAD_URL", releases_url)
    whatsapp = os.getenv("OWNER_WHATSAPP_NUMBER", "254112323814")
    maps_url = "https://maps.app.goo.gl/iqoFy4be7SWYxCuJ8"

    # Only show "Open Web App" when a Flet web server is actually hosted.
    # Otherwise fall back to in-page downloads / the releases page so the
    # landing page never links to a 404.
    if web_app:
        web_nav = f'<a href="{web_app}" class="nav-cta">Open Web App</a>'
        web_hero = f'<a href="{web_app}" class="btn btn-primary">Open Web App</a>'
        dl_hero = '<a href="#downloads" class="btn btn-ghost">Download the App</a>'
        web_dl_card = (
            '<div class="card dl-card">'
            '<span class="tag">Web</span>'
            '<h3>Web App</h3>'
            '<p>Nothing to install. Open the shop in your browser and start ordering.</p>'
            f'<a href="{web_app}" class="btn btn-primary">Open in Browser</a>'
            '</div>'
        )
        web_foot = f'<a href="{web_app}">Web App</a>'
        downloads_sub = (
            "Use the web app instantly, or install the Android / desktop app "
            "for the full experience."
        )
    else:
        web_nav = '<a href="#downloads" class="nav-cta">Download App</a>'
        web_hero = '<a href="#downloads" class="btn btn-primary">Download the App</a>'
        dl_hero = ""
        web_dl_card = ""
        web_foot = f'<a href="{releases_url}">Releases</a>'
        downloads_sub = (
            "Download the Android APK or the desktop app to start shopping."
        )

    html = (
        _LANDING_PAGE
        .replace("__WEB_NAV__", web_nav)
        .replace("__WEB_HERO__", web_hero)
        .replace("__DL_HERO__", dl_hero)
        .replace("__WEB_DL_CARD__", web_dl_card)
        .replace("__WEB_FOOT__", web_foot)
        .replace("__DOWNLOADS_SUB__", downloads_sub)
        .replace("__APK_URL__", apk_url)
        .replace("__DESKTOP_URL__", desktop_url)
        .replace("__WHATSAPP_URL__", f"https://wa.me/{whatsapp}")
        .replace("__MAPS_URL__", maps_url)
        .replace("__REPO_URL__", repo)
    )
    return HTMLResponse(content=html)


@app.get("/health", status_code=200)
@app.head("/health", status_code=200)
async def health_check():
    return "ok"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
