"""
Order, tracking, and payment-refresh endpoints for the customer API.

Requires backend/001_endpoint_hardening.sql, and `supabase` must be the SERVICE-ROLE client.
"""
import logging
import re
from typing import Any, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.daraja_service import DarajaService
from app.db.supabase_client import supabase_admin as supabase  # service-role client (bypasses RLS)
from app.core.rate_limiter import limiter
from app.core.auth_deps import get_current_user

log = logging.getLogger("orders")
router = APIRouter()


# --------------------------------------------------------------- helpers
def normalize_msisdn(raw: str) -> str:
    """Return 2547XXXXXXXX / 2541XXXXXXXX or raise 400."""
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 10 and d.startswith("0"):
        d = "254" + d[1:]
    elif len(d) == 9 and d[0] in "17":
        d = "254" + d
    if not re.fullmatch(r"254[17]\d{8}", d):
        raise HTTPException(status_code=400, detail="Enter a valid Kenyan phone number.")
    return d


def _is_mpesa(method: str) -> bool:
    m = re.sub(r"[^a-z]", "", (method or "").lower())
    return m in {"mpesa", "mpesastk", "mpesastkpush"} or (
        "mpesa" in m and ("stk" in m or "push" in m)
    )


# ----------------------------------------------------- shared order service
async def place_order_and_charge(
    *,
    customer_id: Optional[str],
    phone: str,
    fulfillment: str,
    location: str,
    delivery_address: str,
    payment_method: str,
    items: List[dict],          # [{"id": product_id, "qty": int}]
    channel: str = "app",       # app | web | pos | whatsapp
    sold_by: Optional[str] = None,   # staff_users.id
) -> dict:
    """Used by the website/app checkout AND by WhatsApp staff selling.
    Prices, delivery fee, stock: all decided in the database, never by the caller."""
    phone = (
        normalize_msisdn(phone)
        if phone or _is_mpesa(payment_method)
        else "walk-in"
    )
    if not items or len(items) > 30:
        raise HTTPException(400, "Invalid cart.")
    for item in items:
        try:
            quantity = int(item.get("qty", 0))
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid cart.")
        if not str(item.get("id", "")).strip() or not 1 <= quantity <= 1000:
            raise HTTPException(400, "Invalid cart.")

    try:
        res = supabase.rpc("create_order", {
            "p_customer_id": customer_id,
            "p_phone": phone,
            "p_fulfillment": fulfillment,
            "p_location": location or "",
            "p_delivery_address": (delivery_address or "").strip()[:300],
            "p_payment_method": payment_method,
            "p_channel": channel,
            "p_sold_by": sold_by,
            "p_items": [{"id": i["id"], "qty": int(i["qty"])} for i in items],
        }).execute()
    except Exception as e:
        msg = str(e)
        if "out_of_stock" in msg:
            raise HTTPException(409, "One or more items are out of stock.")
        if "unknown_delivery_zone" in msg:
            raise HTTPException(400, "We don't deliver to that location yet.")
        if "unknown_product" in msg:
            raise HTTPException(400, "One or more cart items are no longer available.")
        if "bad_qty" in msg or "empty_cart" in msg:
            raise HTTPException(400, "Invalid cart.")
        log.exception("create_order failed")
        raise HTTPException(500, "Could not create the order. Please try again.")

    order = cast(dict[str, Any], res.data[0] if isinstance(res.data, list) else res.data)
    if not order:
        raise HTTPException(500, "Could not create the order. Please try again.")

    checkout_id = ""
    if _is_mpesa(payment_method):
        try:
            stk = await DarajaService().send_stk_push(
                phone_number=phone,
                amount=int(round(float(order["total_amount"]))),
                account_reference=order["order_reference"],
                transaction_desc="Auto Parts Order",
            )
            checkout_id = (stk or {}).get("CheckoutRequestID", "")
            if not checkout_id:
                raise RuntimeError(f"No CheckoutRequestID in response: {stk}")
            linked = supabase.table("orders").update(
                {"checkout_request_id": checkout_id}
            ).eq("id", order["id"]).eq("payment_status", "pending").select("id").execute()
            if not getattr(linked, "data", None):
                raise RuntimeError("Could not link the STK request to the order.")
        except Exception:
            log.exception("STK push failed for %s", order["order_reference"])
            # No fake 'sim_' ids: cancel the order and give the stock back.
            supabase.rpc("release_order_stock",
                         {"p_order_id": order["id"], "p_new_status": "Payment Failed"}).execute()
            raise HTTPException(502, "Could not start the M-Pesa payment. You were not charged. Try again.")

    return {
        "order": order,
        "checkout_request_id": checkout_id,
    }


# -------------------------------------------------------------- endpoints
class CartLine(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    qty: int = Field(ge=1, le=1000)


class CheckoutRequest(BaseModel):
    # Extra fields (price, total, customer_id) sent by old clients are ignored.
    phone: str = Field(default="", max_length=32)
    fulfillment: str = Field(min_length=1, max_length=40)
    location: str = Field(default="", max_length=120)
    delivery_address: str = Field(default="", max_length=300)
    payment_method: str = Field(min_length=1, max_length=40)
    items: List[CartLine] = Field(min_items=1, max_items=30)


@router.post("/checkout", status_code=201)
@limiter.limit("5/minute")
async def process_checkout(request: Request, payload: CheckoutRequest,
                           user: dict = Depends(get_current_user)):
    if not payload.items or len(payload.items) > 30:
        raise HTTPException(400, "Invalid cart.")
    if payload.fulfillment.lower() not in ("pickup", "delivery"):
        raise HTTPException(400, "Invalid fulfillment option.")
    result = await place_order_and_charge(
        customer_id=str(user["id"]),
        phone=payload.phone,
        fulfillment=payload.fulfillment,
        location=payload.location,
        delivery_address=payload.delivery_address,
        payment_method=payload.payment_method,
        items=[i.dict() for i in payload.items],
        channel="app",
    )
    order = result["order"]
    return {
        "status": "success",
        "message": "STK prompt sent to phone" if result["checkout_request_id"] else "Order received",
        "order_id": order["order_reference"],
        "total": float(order["total_amount"]),   # the app must show THIS total
        "checkout_request_id": result["checkout_request_id"],
    }


class TrackRequest(BaseModel):
    order_reference: str
    phone: str


@router.post("/track")
@limiter.limit("10/minute")
async def track_order(request: Request, body: TrackRequest):
    """Public tracking needs the reference AND the phone used on the order.
    Returns status only: no receipt numbers, no item list, no other orders."""
    phone = normalize_msisdn(body.phone)
    ref = (body.order_reference or "").strip().upper()
    res = supabase.table("orders").select(
        "order_reference,status,payment_status,fulfillment,created_at,total_amount"
    ).eq("order_reference", ref).eq("customer_phone", phone).limit(1).execute()
    rows = res.data or []
    if not rows:
        # same answer whether the ref or the phone was wrong
        raise HTTPException(404, "No matching order.")
    return {"status": "success", "order": cast(dict[str, Any], rows[0])}


def _get_owned_order(order_ref: str, user: dict) -> dict[str, Any]:
    res = supabase.table("orders").select("*") \
        .eq("order_reference", (order_ref or "").strip().upper()).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(404, "Order not found.")
    row = cast(dict[str, Any], rows[0])
    if str(row.get("customer_id")) != str(user.get("id")):
        raise HTTPException(404, "Order not found.")
    return row


@router.get("/status/{order_ref}")
async def get_order_status(order_ref: str, user: dict = Depends(get_current_user)):
    o = _get_owned_order(order_ref, user)
    return {
        "order_reference": o["order_reference"],
        "status": o.get("status"),
        "payment_status": o.get("payment_status"),
        "receipt_number": o.get("receipt_number") or "",
    }


@router.post("/{order_ref}/refresh-payment")
@limiter.limit("6/minute")
async def refresh_payment(request: Request, order_ref: str,
                          user: dict = Depends(get_current_user)):
    """Replaces /verify-receipt. NEVER accepts a typed receipt. If the callback
    was lost, ask Daraja directly about this order's own CheckoutRequestID."""
    o = _get_owned_order(order_ref, user)
    if o.get("payment_status") == "paid":
        return {"status": "success", "message": "Payment already confirmed."}

    checkout_id = str(o.get("checkout_request_id") or "").strip()
    if not checkout_id:
        raise HTTPException(400, "No M-Pesa payment was started for this order.")

    try:
        q = await DarajaService.query_stk_status(checkout_id)
    except Exception:
        log.exception("STK query failed")
        raise HTTPException(502, "Could not reach M-Pesa. Try again shortly.")

    q_data = cast(dict[str, Any], q) if isinstance(q, dict) else {}
    code = str(q_data.get("ResultCode", ""))
    if code == "0":
        # STK Query has no receipt/amount; the amount is what WE requested for this id.
        result = supabase.rpc("mark_order_paid", {"p_checkout_id": checkout_id}).execute()
        paid_order = result.data[0] if isinstance(result.data, list) and result.data else result.data
        if not paid_order or paid_order.get("payment_status") != "paid":
            raise HTTPException(409, "M-Pesa confirmed, but the order could not be updated.")
        return {"status": "success", "message": "Payment confirmed by M-Pesa."}
    if code == "1032":
        supabase.rpc("release_order_stock",
                     {"p_order_id": o["id"], "p_new_status": "Cancelled"}).execute()
        raise HTTPException(400, "The payment was cancelled.")
    raise HTTPException(400, "Payment not completed yet. Check your phone or retry shortly.")


# ------------------------------------------------- kept from the old file
@router.get("/user/{identifier}")
async def get_user_orders(identifier: str, current_user: dict = Depends(get_current_user)):
    try:
        orders_list = []
        clean_id = (identifier or "").strip()

        if not clean_id or clean_id in ["None", "null", "undefined"]:
            return {"status": "success", "orders": []}

        # Only allow a user to read their own orders (by id or email)
        token_id = str(current_user.get("id", ""))
        token_email = str(current_user.get("email") or "").lower()
        if clean_id != token_id and clean_id.lower() != token_email:
            raise HTTPException(status_code=403, detail="You can only view your own orders.")

        # 1. If it looks like a UUID, query customer_id directly
        if len(clean_id) > 30 and "-" in clean_id:
            res = supabase.table("orders").select("*").eq("customer_id", clean_id).order("created_at", desc=True).execute()
            orders_list = res.data if hasattr(res, "data") else []

        # 2. If it's an email, find the user ID from customers table
        if not orders_list and "@" in clean_id:
            cust_res = supabase.table("customers").select("id").ilike("email", clean_id).execute()
            cust_data = getattr(cust_res, "data", None) or []
            if cust_data and isinstance(cust_data, list):
                real_id = cust_data[0].get("id")
                res2 = supabase.table("orders").select("*").eq("customer_id", real_id).order("created_at", desc=True).execute()
                orders_list = res2.data if hasattr(res2, "data") else []

        return {"status": "success", "orders": orders_list}
    except HTTPException:
        raise
    except Exception:
        log.exception("Fetch user orders error")
        raise HTTPException(status_code=500, detail="Could not load orders.")
