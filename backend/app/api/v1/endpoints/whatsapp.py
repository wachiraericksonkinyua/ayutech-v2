"""
Replacement for backend/app/api/v1/endpoints/whatsapp.py

Env: META_APP_SECRET, WHATSAPP_VERIFY_TOKEN, CRON_SECRET, ADMIN_WHATSAPP_PHONE
pip: bcrypt
Staff phones in staff_users.phone must be stored as 2547XXXXXXXX (same format as Meta's `from`).

Identity model:  Meta authenticates the sender's number -> we trust `from`
ONLY because the webhook signature is verified.  A PIN adds a second factor
(SIM-swap / stolen-phone protection).  The AI never decides prices or payments.
"""
import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response

from app.db.supabase_client import supabase_admin as supabase  # service-role client (bypasses RLS)
from app.services.whatsapp import send_whatsapp_message, WHATSAPP_TOKEN
from app.services.vision_service import get_whatsapp_media_url
from app.services.triage import run_triage
from app.api.v1.endpoints.orders import place_order_and_charge  # adjust path

log = logging.getLogger("whatsapp")
router = APIRouter()

APP_SECRET = os.getenv("META_APP_SECRET", "")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")
ADMIN_PHONE = os.getenv("ADMIN_WHATSAPP_PHONE", "")
MANAGER_ROLES = {"admin", "owner", "manager"}


def _valid_signature(raw: bytes, header: str | None) -> bool:
    if not APP_SECRET or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if VERIFY_TOKEN and hub_mode == "subscribe" and hmac.compare_digest(hub_token or "", VERIFY_TOKEN):
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@router.post("/webhook")
async def whatsapp_webhook(request: Request, background: BackgroundTasks,
                           x_hub_signature_256: str | None = Header(None)):
    raw = await request.body()
    if not _valid_signature(raw, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Bad signature")
    try:
        data = json.loads(raw)
        value = ((data.get("entry") or [{}])[0].get("changes") or [{}])[0].get("value") or {}
        messages = value.get("messages") or []
    except Exception:
        return {"status": "ignored"}

    for msg in messages:                                   # `continue`, never `return`, inside this loop
        msg_id = msg.get("id")
        from_phone = (msg.get("from") or "").strip().replace("+", "")
        if not msg_id or not from_phone:
            continue
        try:  # Meta retries on slow replies: process each message id once
            supabase.table("processed_webhook_messages").insert({"msg_id": msg_id}).execute()
        except Exception as exc:
            if getattr(exc, "code", None) == "23505" or "23505" in str(exc) or "duplicate key" in str(exc).lower():
                continue
            log.exception("Could not persist WhatsApp message ID %s", msg_id)
            raise HTTPException(status_code=503, detail="Webhook storage is unavailable.")
        background.add_task(_handle_message, msg, from_phone)

    return {"status": "received"}   # answer Meta fast; work happens in the background


# --------------------------------------------------------------- routing
async def _handle_message(msg: dict, from_phone: str):
    try:
        mtype = msg.get("type", "")
        text, media_id = "", ""
        if mtype == "text":
            text = (msg.get("text") or {}).get("body", "")
        elif mtype == "image":
            img = msg.get("image") or {}
            text, media_id = (img.get("caption") or "").strip(), img.get("id", "")
        if not text and not media_id:
            return

        staff = _find_staff(from_phone)
        if staff and mtype == "text":
            reply = await _staff_flow(staff, from_phone, text)
            await send_whatsapp_message(from_phone, reply)
            return

        # ---- customer path: your existing AI triage (it only PROPOSES; code decides)
        image_url = await get_whatsapp_media_url(media_id, WHATSAPP_TOKEN) if media_id else ""
        result = await run_triage(
            message=text or "[Image attached - identify and respond to the part in this photo]",
            customer_phone=from_phone, image_url=image_url, source="whatsapp")
        if result.get("reply"):
            await send_whatsapp_message(from_phone, result["reply"])
    except Exception:
        log.exception("WhatsApp handler error for %s", from_phone)
        await send_whatsapp_message(
            from_phone, "Habari! Nimekupokea, anayeshughulikia ataweza kukujibu hivi karibuni. Asante!")


# ------------------------------------------------------------ staff mode
def _find_staff(phone: str):
    r = supabase.table("staff_users").select(
        "id,name,role,pin_hash,pin_failed_attempts,pin_locked_until"
    ).eq("active", True).execute()
    phone_core = re.sub(r"\D", "", phone)[-9:]
    return next(
        (staff for staff in (r.data or [])
         if phone_core and re.sub(r"\D", "", str(staff.get("phone") or ""))[-9:] == phone_core),
        None,
    )


def _has_session(staff_id: str, phone: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    r = supabase.table("whatsapp_staff_sessions").select("id") \
        .eq("staff_id", staff_id).eq("phone", phone).gt("expires_at", now).limit(1).execute()
    return bool(r.data)


def _login(staff: dict, phone: str, pin: str) -> str:
    now = datetime.now(timezone.utc)
    locked = staff.get("pin_locked_until")
    if locked and datetime.fromisoformat(locked.replace("Z", "+00:00")) > now:
        return "Too many wrong PINs. Try again in 15 minutes."
    ok = bool(staff.get("pin_hash")) and bcrypt.checkpw(pin.encode(), staff["pin_hash"].encode())
    if not ok:
        fails = (staff.get("pin_failed_attempts") or 0) + 1
        upd = {"pin_failed_attempts": fails}
        if fails >= 5:
            upd = {"pin_failed_attempts": 0,
                   "pin_locked_until": (now + timedelta(minutes=15)).isoformat()}
        supabase.table("staff_users").update(upd).eq("id", staff["id"]).execute()
        return "Wrong PIN."
    supabase.table("staff_users").update(
        {"pin_failed_attempts": 0, "pin_locked_until": None}).eq("id", staff["id"]).execute()
    supabase.table("whatsapp_staff_sessions").insert({
        "staff_id": staff["id"], "phone": phone,
        "expires_at": (now + timedelta(hours=8)).isoformat()}).execute()
    return f"Unlocked, {staff['name']}. Commands:\nsell <part#> x<qty> <customer phone>\nsales"


async def _staff_flow(staff: dict, phone: str, text: str) -> str:
    t = text.strip()
    low = t.lower()

    if low.startswith("pin "):
        return _login(staff, phone, t[4:].strip())
    if not _has_session(staff["id"], phone):
        return "Staff mode locked. Send: PIN <your pin>"

    if low in ("sales", "sales today", "report"):
        if staff["role"] not in MANAGER_ROLES:
            return "Only managers can see the sales report."
        return _format_report()

    m = re.fullmatch(r"sell\s+(\S+)\s+x?(\d{1,3})\s+(\S+)", t, flags=re.I)
    if m:
        code, qty, cust_phone = m.group(1), int(m.group(2)), m.group(3)
        prod = supabase.table("products").select("id,name,price") \
            .eq("part_number", code).limit(1).execute().data
        if not prod:
            return f"Part number {code} not found."
        try:
            res = await place_order_and_charge(
                customer_id=None, phone=cust_phone, fulfillment="pickup", location="",
                delivery_address="", payment_method="M-Pesa",
                items=[{"id": prod[0]["id"], "qty": qty}],
                channel="whatsapp", sold_by=staff["id"])
        except HTTPException as e:
            return f"Could not sell: {e.detail}"
        o = res["order"]
        return (f"{o['order_reference']}: {qty} x {prod[0]['name']} = KES {float(o['total_amount']):,.0f}. "
                f"M-Pesa prompt sent to {cust_phone}.")

    return "Commands:\nsell <part#> x<qty> <customer phone>\nsales"


def _format_report(day: str | None = None) -> str:
    rows = supabase.rpc("daily_sales_report", {"p_day": day} if day else {}).execute().data or []
    if not rows:
        return "No paid sales yet today."
    lines = [f"{r['seller']} ({r['channel']}): {r['orders_count']} sales, KES {float(r['total']):,.0f}"
             for r in rows]
    grand = sum(float(r["total"]) for r in rows)
    return "Sales today\n" + "\n".join(lines) + f"\nTOTAL: KES {grand:,.0f}"


# ----------------------------------------------------- evening admin report
@router.post("/internal/daily-report")
async def daily_report(x_cron_secret: str | None = Header(None)):
    """Call from a Render Cron Job / GitHub Action at ~18:30 EAT with header X-Cron-Secret.
    NOTE: free-form WhatsApp messages only deliver if the admin messaged you in the last
    24h. For a guaranteed evening delivery, switch this to an approved template message."""
    if not CRON_SECRET or not x_cron_secret or not hmac.compare_digest(x_cron_secret, CRON_SECRET):
        raise HTTPException(404)
    if not ADMIN_PHONE:
        raise HTTPException(500, "ADMIN_WHATSAPP_PHONE not set")
    await send_whatsapp_message(ADMIN_PHONE, _format_report())
    return {"status": "sent"}