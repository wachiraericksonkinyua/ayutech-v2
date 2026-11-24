# AyuTech Motors — Repository Handoff

This document describes the code in this repository as inspected on 2026-11-24 and records the agreed product direction below. It is intended as portable context for an agent working on the companion app/repository; it is not a full security audit.

## What this repository is

A Python/Flet customer shopping app and a separate staff point-of-sale (POS) app, backed by a FastAPI API and Supabase. It is an extension of the AyuTech Motors spare-parts business: product browsing, checkout, M-Pesa, order tracking, customer profiles, staff inventory/order operations, and AI-assisted fitment/WhatsApp support are represented in code.

The customer and staff apps are distinct Flet entry points. They call the deployed API URL `https://ayutech-v2.onrender.com/api/v1` (also repeated in UI state), rather than deriving it from a configurable client setting.

## Repository map

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI application, middleware, API router registration, landing page, health endpoint, optional Flet customer web mount at `/shop`. |
| `backend/app/api/v1/endpoints/` | HTTP handlers for catalog, customer orders, payments, reviews, AI/triage, WhatsApp webhook, and staff/admin operations. |
| `backend/app/routers/auth.py` | Customer registration/login, OAuth and password recovery callbacks, profile read/update and image upload. |
| `backend/app/core/` | Environment configuration, auth dependencies, token/password helpers, in-memory product TTL cache, rate limiter, and scheduler. |
| `backend/app/db/supabase_client.py` | Public Supabase client and required server-side service-role client. |
| `backend/app/models/schemas.py` | Small shared checkout/order schema set; many endpoints define their own request models. |
| `backend/app/services/` | Daraja/M-Pesa, AI catalog chat and WhatsApp triage, vision, WhatsApp sending, delivery fee helper, and reporting. |
| `backend/app/ui/` | Customer Flet app, shared UI state/API/theme helpers, and views. |
| `backend/app/dashboard.py` | Main, standalone staff management/POS Flet app. |
| `backend/store.py` | Older standalone customer-store prototype; its API paths do not match the current API. It is not the target of the supplied launch scripts. |
| `backend/main.py` | Flet packaging entry point for the customer client; not the FastAPI ASGI app. |
| `launch_customer.sh`, `launch_pos.sh` | Local launchers for `app/ui/main_app.py` and `app.dashboard`, respectively. |
| `backend/pyproject.toml`, `backend/pubspec.yaml` | Flet client build metadata/dependencies. |
| `backend/requirements.txt` | Backend Python dependencies (also includes Flet). |
| `backend/*.sql` | Manually applied Supabase setup/migration scripts for customers, staff, reviews, delivery address, and indexes. |
| `backend/seed_db.py`, `seed_toyota_diesel.py`, `seed_data.json` | Product seed/import support and sample data. `seed_db.py` imports category data from a separate public GitHub repository. |
| `.github/workflows/build-app.yml` | Tag/manual workflow to build Android, Linux, and Windows customer-client packages and publish release assets. Windows is allowed to fail without blocking the other builds. |

There are no repository README, test suite, API/backend deploy workflow, database migration verified against the live Supabase schema, or standard local-development configuration file checked in. `backend/draft/001_endpoint_hardening.sql` is an unapplied draft and must not be applied over the existing database schema. The ordered scripts in `backend/migrations/` still require review and execution in the intended environment; `003_refill_rpc.sql` contains the missing refill RPC. `backend/.env` exists in the working copy and is ignored; its values were not inspected. `backend/debug_downloaded_part.jpg` is a tracked debug artifact.

## What is implemented

### Customer client

`backend/app/ui/main_app.py` owns navigation and shared cart/wishlist/session state. The customer app has four bottom-navigation tabs: Home, Browse, Cart, and Account. Order history, settings, wishlist, and tracking are reached as subviews from Account. The standalone staff POS is a separate app.

- **Home and browse:** load public products from `/products/`, show featured items, search/filter by a fixed category list, and provide fallback products if the API returns nothing.
- **Product details:** image, category/description, quantity, add-to-cart, call/WhatsApp/AI fitment actions, and review display/submission.
- **Cart/checkout:** pickup or delivery, delivery-zone options, saved-address UI, M-Pesa STK or cash-on-pickup selection, server-calculated order totals, and payment status refresh. Checkout sends customer authentication and only product IDs/quantities; it no longer accepts client-supplied prices or receipt codes.
- **Orders:** authenticated order list with receipt/details and background status polling, nested under Account.
- **Hub/profile:** email/password registration and login, Google/OAuth flow, password reset, onboarding, profile fields, saved addresses, avatar/banner uploads, wishlist, and public phone-based order tracking.
- **AI:** in-app chat calls `/ai/chat`; assistant replies can include suggested products and add-to-cart actions. Theme toggle, notifications, and floating draggable assistant button are present.

Most UI state is process/session memory. Cart, wishlist, notifications and order cache are not clearly persisted locally across app restarts.

### Staff/POS client

`backend/app/dashboard.py` is the full management app launched by `launch_pos.sh`. It includes email/password and PIN login, then staff-token-authenticated screens for:

- live orders and fulfillment;
- leads and human takeover;
- product inventory, edits, stock adjustments and refill requests;
- multi-item counter POS, cash/manual payment recording, and M-Pesa STK; prices and stock are finalized by the backend, not by the desktop cart;
- daily-sales reporting and staff account administration.

`backend/app/ui/views/dashboard_view.py` remains a separate compact admin-orders view in the source tree; it is no longer wired into customer navigation.

### API and integrations

`backend/app/main.py` registers:

- `/api/v1/admin/*` — staff-authenticated orders, products, leads, staff, refills and analytics;
- `/api/v1/orders/*` — authenticated customer checkout and own-order/status/payment-refresh operations; public tracking requires order reference plus phone;
- `/api/v1/payments/*` — POS STK initiation and M-Pesa callbacks;
- `/api/v1/products/*` — public catalog, authenticated product creation, product-image upload;
- `/api/v1/reviews/*` — review read/write;
- `/api/v1/ai/*` — fitment chat and triage;
- `/api/v1/whatsapp/*` — Meta webhook and inbound AI response;
- `/api/v1/auth/*` — customer auth, OAuth/recovery, profile and image upload.

The root serves a marketing landing page/API metadata, `/health` is a basic health response, and `/docs` is FastAPI’s generated documentation.

Major external services are Supabase (Auth, Postgres, Storage), Safaricom Daraja (M-Pesa STK), Meta WhatsApp Cloud API, Groq (text/vision), and optionally OpenRouter (vision fallback). The AI path can search public product fields, record leads/conversations/out-of-stock demand, and pause WhatsApp replies when a lead is marked `human_takeover`.

### Data model implied by code

The code expects Supabase tables `products`, `orders`, `customers`, `reviews`, `staff_users`, `leads`, `conversations`, `stock_wishlist`, `refill_requests`, and `system_logs`, plus Storage buckets including `product-images`, `profile-images`, and `chat_image`. The unapplied `backend/draft/001_endpoint_hardening.sql` is historical reference only and may conflict with the current database schema. Current migrations under `backend/migrations/` include order/POS changes and `003_refill_rpc.sql`; they are not confirmed applied to a live Supabase project.

## Session changes (2026-11-24)

This section records the backend, POS, and customer-shop changes made during this session. It describes working-tree code, not a deployed release.

### Backend and database

| Area | Changes |
|---|---|
| Supabase client | Admin endpoints now consistently use the service-role client. `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY` is required; the previous fallback to the public key was removed. |
| Staff PIN login | Added phone normalization, bcrypt hash verification, five-failure lockout for 15 minutes, failure reset on success, rate limiting, and staff JWT issuance. Email/password login uses a separate Supabase client so its user session cannot leak into the shared client. |
| Orders and POS | Customer and POS order creation use the `create_order` RPC, intended to set database prices, delivery fee, and stock atomically. Manual POS payments use `mark_order_paid_manual`; cancellation/failed payment uses `release_order_stock`. The compatibility `/admin/orders` route now validates a POS cart and delegates to the same server-side flow instead of inserting arbitrary totals/items. |
| Order access and payment refresh | Customer checkout and order status require customer authentication and ownership. Public tracking requires both order reference and phone and returns limited status fields. Client-entered receipt verification was removed; refresh checks the order's own Daraja checkout ID and uses the payment RPC. |
| M-Pesa | POS STK initiation accepts an existing pending order ID and phone, reads the amount from that order, and links the checkout ID to the pending order. Callback processing checks the secret path, records transactions, asks Daraja to confirm success, and invokes an idempotent/amount-checked payment RPC. The paid-order WhatsApp notifier now imports from the actual `app.services.whatsapp` module. |
| Daraja configuration | The old unprotected `/payments/callback` fallback was removed. The callback URL must match `/api/v1/payments/mpesa-callback/{MPESA_CALLBACK_SECRET}`; it can be assembled from `BACKEND_PUBLIC_URL` or `RENDER_EXTERNAL_URL` plus the secret. |
| WhatsApp | Webhooks validate Meta's HMAC signature, deduplicate message IDs, and process messages in background tasks. The staff flow uses active staff, normalized phone matching, PIN lockout and expiring sessions; staff sales go through the shared order transaction. Manager reports use `daily_sales_report`. |
| Refill and validation | Refill inputs, POS items, and product inputs have validation limits. Refill status/stock updates now call a database RPC instead of separate read/write steps. Order status updates cannot set payment state or fulfill an unpaid order. |
| Database migration | The old `backend/draft/001_endpoint_hardening.sql` was not applied and may conflict with the existing schema. `backend/migrations/003_refill_rpc.sql` defines the missing `fulfill_refill_request` function; it must still be run in Supabase before refill fulfillment can work. |

The migration expects existing `orders`, `products`, and `staff_users` tables. It assumes UUID order/staff IDs and uses text for product IDs so they can be UUIDs or integers. Verify actual column types, existing data, RLS, and constraints in staging before applying it anywhere; SQL parsing is not a database integration test.

### Customer shop and POS interface

- Reduced the floating customer navigation to four destinations: Home, Browse, Cart, and Account. Existing callbacks targeting the old Hub index are mapped to Account.
- Moved the orders list into Account as a subview, added an Account “My Orders” entry, and made the order view return to Account. The cart confirmation now opens that subview.
- Added responsive sizing: desktop windows open at a usable size, the dock is centered and capped in width, shop content is centered/capped at 1280px, and the draggable AI button repositions and stays in the viewport on resize.
- Updated customer checkout to send a bearer token, only item IDs/quantities, the selected delivery zone, and supported fulfillment values. Failed requests now keep the cart and show an error instead of inventing a local successful order.
- Replaced manual receipt-code entry in checkout/orders with authenticated M-Pesa status refresh. Saved-address/profile reads and order status polling now use the shared authenticated API client.
- Updated public tracking UI to request both the order reference and phone, matching the backend's limited tracking response.
- Reworked the standalone POS checkout to call `/admin/pos/sale` once for cash, manual, and M-Pesa sales. It no longer makes client-side stock deductions, creates a duplicate order, or sends a client total/checkout ID to the STK route. Displayed POS prices are read-only.
- Customer and POS clients can override the default API base URL with `AYUTECH_API_BASE_URL`; `main_app.py` no longer shadows the shared state setting with its own hard-coded constant.

### Package compatibility and checks

- In the local backend virtual environment, the incompatible FastAPI `0.99.1` / Pydantic `1.10.15` attempt was reverted. The environment was restored to FastAPI `0.141.1` and Pydantic `2.13.4`, compatible with installed Supabase/Google packages; `pip check` reported no broken requirements, and importing `app.main` confirmed `/shop` mounted.
- `backend/requirements.txt` now pins the tested direct dependencies, including FastAPI/Pydantic, `bcrypt==4.0.1` (below v5), and APScheduler.
- Python compilation, endpoint/UI imports, focused request validation, SQL/PL/pgSQL grammar parsing, and `git diff --check` passed. No automated test suite or live Supabase/Daraja integration test was run.
- Render environment settings could not be inspected or changed from this workspace. Verify/add the names `MPESA_CALLBACK_SECRET`, `META_APP_SECRET`, `CRON_SECRET`, `ADMIN_WHATSAPP_PHONE`, and `ADMIN_SECRET_KEY`; configure `DARAJA_CALLBACK_URL` to the secret-bearing callback path, or set `BACKEND_PUBLIC_URL`/Render's public URL plus `MPESA_CALLBACK_SECRET`.

### Worktree notes

- `backend/app/routers/auth.py` already had an unrelated uncommitted edit before this endpoint/UI repair and was not changed as part of this work.
- No migration was applied, no deployment was performed, and no commit was created. Service-role credentials and payment/webhook secrets must remain backend-only.

## Agreed product direction: add / cut / park

These are the project owner's intended direction; implementation status is summarized in the session changes above and the remaining gaps below.

### Add

- **Staff roles:** standardize `admin`, `cashier`, and `seller` roles, with explicit server-side authorization for each operation. Keep staff identity distinct from customer identity.
- **Low-stock WhatsApp alert:** notify the configured admin when inventory reaches the agreed threshold; make notification behavior configurable and avoid repeated alert spam.
- **Configurable API URL:** `AYUTECH_API_BASE_URL` now overrides the default production API base for customer and POS clients; set it per local/staging/production build without embedding server secrets in client builds.

### Cut or defer

- **Archive/remove `backend/store.py`:** it is an older customer-store prototype and its API paths do not match the current backend. Confirm no one still launches it before deleting.
- **Remove the unused customer-app dashboard view:** `backend/app/ui/views/dashboard_view.py` is a compact admin screen in the source tree, separate from the main POS dashboard. Keep staff operations in the standalone POS app unless a real customer-app use case is confirmed.
- **Remove `backend/debug_downloaded_part.jpg`:** tracked debug artifact, not product/runtime content.
- **Keep `.env` out of Git:** confirmed ignored, not currently tracked, and absent from the available commit history. If a separate clone/history shows otherwise, treat its secrets as exposed and rotate them.
- **Storefront decision deferred:** retain Flet for now. If SEO or mobile-web performance becomes a priority, evaluate a Vue storefront alongside the Vue admin so those clients can share code. This is optional and should be decided later, not bundled into the backend hardening work.

## Important implementation gaps to resolve

These are observations from the current source, not a claim that nothing exists in the companion app or deployment configuration.

### P0 — checkout/payment correctness and trust boundaries

1. `/orders/checkout` requires customer auth and calls `create_order` for server-side prices, delivery rates, stock reservation, and order creation. The existing database already has the order/payment RPCs; the obsolete `backend/draft/001_endpoint_hardening.sql` is not to be applied. The API must have `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY`.
2. `POST /orders/track` requires the order reference and checkout phone; `/orders/status/{order_ref}` and payment refresh require customer auth. The Flet cart, orders, and tracking views now use these routes and send auth where required.
3. Configure Daraja’s `DARAJA_CALLBACK_URL` to the secret-bearing `/payments/mpesa-callback/{secret}` route, or provide `BACKEND_PUBLIC_URL`/Render's public URL and `MPESA_CALLBACK_SECRET`. The STK client rejects a callback URL that does not match that route.
4. Customer checkout failures now preserve the cart and report the backend error instead of creating a fake local order.

### P1 — authorization, route and data consistency

- `/products/` product creation only requires a normal customer token; staff authorization is separately implemented under `/admin/products`. Decide whether customer creation is intended and enforce the intended role.
- Reviews are only purchase-checked if `customer_id` is supplied; the endpoint does not require an authenticated identity. Verify identity and purchase server-side for every review.
- Public tracking requires the reference and phone and returns limited order fields; confirm that this matches the intended privacy policy.
- Refill fulfillment calls `fulfill_refill_request` to update the request and product stock atomically. The function is in `backend/migrations/003_refill_rpc.sql` and still needs to be run in Supabase.
- POS cash/manual payments call `mark_order_paid_manual`; payment audit and manual-payment RPC schema are included in the migration and still require staging deployment.
- Delivery fees, product prices, and stock are computed by the database RPC. The UI sends only the selected delivery zone and item IDs/quantities.
- New order references use a database sequence and unique index; old rows are backfilled where possible.
- The legacy `/admin/orders` insert is retained only as a compatibility route and now uses the server-priced POS transaction flow.
- `backend/store.py` uses older endpoint paths such as `/payments/orders/create`, `/payments/stk-push`, and `/admin/products`; these are not the current route set. Keep it explicitly archived or update it if still needed.

### P1 — production reliability and operations

- `start_scheduler()` is defined but is not called by application startup. The 24-hour lead follow-up job therefore is not wired in this repository. `apscheduler` is also absent from `requirements.txt`.
- `generate_daily_failure_report()` is implemented but has no caller found.
- OAuth/recovery one-time tokens are held in process memory for five minutes. They will be lost on restart and are not shared across multiple workers.
- Customer and POS default to the production API URL, but can target local/staging APIs with `AYUTECH_API_BASE_URL`.
- `payment_audit` records manual payment details, but there is no general before/after audit trail for staff price and stock changes. Low-stock WhatsApp alerts are also not implemented.
- The API has a basic health endpoint, but no readiness check for Supabase, Daraja/WhatsApp configuration, or mounted client. The build workflow packages the customer app; no backend deployment workflow is present here.
- SQL setup is spread across overlapping manual scripts. Consolidate it into versioned, ordered migrations and document the expected RLS policies/buckets/table schemas, including all tables used by services.
- Ensure deployment has strong `SECRET_KEY`/admin key, Supabase service-role key where needed, Daraja credentials/callback, WhatsApp credentials/webhook verification token, and AI provider keys. Never package server-only credentials in a Flet client.

### P2 — testing and maintainability

- No tests were found. Add focused API/service tests around checkout totals, payment callback matching/idempotency, auth ownership, staff authorization, status transitions, and client failure handling; use mocked Supabase and external APIs.
- Add a canonical `README`/local setup and environment-variable reference, and separate API/backend dependencies from client build dependencies.
- Several routes and services use broad exception handling, print-only logging, mixed sync/async Supabase operations, and duplicated client/API logic. Add structured logs and consistent error responses where these affect supportability.
- Catalog categories are hard-coded in the client and may diverge from Supabase; derive them from catalog data or validate against one shared source.
- Decide whether the compact `dashboard_view.py` is needed; if so, add an explicit authorized navigation route, otherwise remove it to avoid a dead path.
- Replace the placeholder product images and confirm seed pricing/stock before using sample seed records as live inventory.

## Suggested build sequence

1. Confirm which features belong to this repo versus the companion app, and agree on the shared API/data contract and staff role permissions.
2. Verify the currently supplied migrations against the actual Supabase schema, then run the refill migration `backend/migrations/003_refill_rpc.sql` and test refill fulfillment.
3. Set the required secret names in Render, configure the secret-bearing Daraja callback URL, and run the API and customer UI with the pinned environment.
4. Add general audit logging for price/stock changes and low-stock WhatsApp alerts.
5. Add automated tests and setup/migration docs, then verify customer and POS flows against staging Supabase and Daraja sandbox. Decide separately whether to replace the Flet storefront with Vue based on SEO/mobile-web needs.

## Short context for another agent

> This repository is the AyuTech Motors customer shopping + staff POS extension. Customer UI: Flet at `backend/app/ui/main_app.py` with Home/Browse/Cart/Account bottom tabs; staff POS: `backend/app/dashboard.py`; API: FastAPI at `backend/app/main.py`; data/auth/storage: Supabase. Both clients use `AYUTECH_API_BASE_URL` when set and otherwise default to the production API. Existing order/payment RPCs are present in the database; `backend/migrations/003_refill_rpc.sql` adds the missing refill RPC and needs to be run in Supabase. Do not apply the historical `backend/draft/001_endpoint_hardening.sql` over the existing schema. Manual payments need `mark_order_paid_manual`; Daraja requires a protected callback URL and `MPESA_CALLBACK_SECRET`; backend requires `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY`. Render settings need verification for `MPESA_CALLBACK_SECRET`, `META_APP_SECRET`, `CRON_SECRET`, `ADMIN_WHATSAPP_PHONE`, and `ADMIN_SECRET_KEY`. Backend requirements pin FastAPI 0.141.1, Pydantic 2.13.4 and bcrypt 4.0.1. Archive `backend/store.py` and remove the compact dashboard view/debug image only after confirming they are unused. Do not assume the separate app’s files or feature status are represented here.
