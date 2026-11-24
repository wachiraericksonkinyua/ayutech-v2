"""
Replacement for backend/app/api/v1/endpoints/payments.py

Env:  MPESA_CALLBACK_SECRET  (long random string)
Set the Daraja CallbackURL to:
   https://<your-api>/api/v1/payments/mpesa-callback/<MPESA_CALLBACK_SECRET>
"""
import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.daraja_service import DarajaService
from app.services.whatsapp import send_order_whatsapp_alert
from app.db.supabase_client import supabase_admin as supabase  # service-role client (bypasses RLS)
from app.core.auth_deps import require_admin
from app.api.v1.endpoints.orders import normalize_msisdn
from app.core.rate_limiter import limiter

log = logging.getLogger("payments")
router = APIRouter()
CALLBACK_SECRET = os.getenv("MPESA_CALLBACK_SECRET", "")
ACK = {"ResultCode": 0, "ResultDesc": "Accepted"}


class PosStkRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=32)


@router.post("/pos-stk-push")
@limiter.limit("10/minute")
async def pos_stk_push(request: Request, body: PosStkRequest, staff: dict = Depends(require_admin)):
    res = supabase.table("orders").select(
        "id,order_reference,total_amount,payment_status"
    ).eq("id", body.order_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(404, "Order not found.")
    order = rows[0]
    if order.get("payment_status") == "paid":
        raise HTTPException(409, "Order is already paid.")
    if order.get("payment_status") != "pending":
        raise HTTPException(409, "Order is not awaiting payment.")

    try:
        amount = float(order.get("total_amount") or 0)
        if amount <= 0:
            raise RuntimeError("Order has no payable total.")
        stk = await DarajaService().send_stk_push(
            phone_number=normalize_msisdn(body.phone),
            amount=int(round(amount)),
            account_reference=order["order_reference"],
            transaction_desc="Counter Sale POS",
        )
        checkout_id = (stk or {}).get("CheckoutRequestID", "")
        if not checkout_id:
            raise RuntimeError(f"No CheckoutRequestID: {stk}")
    except HTTPException:
        raise
    except Exception:
        log.exception("POS STK push failed")
        raise HTTPException(502, "Could not start the M-Pesa payment.")

    try:
        update = supabase.table("orders").update({"checkout_request_id": checkout_id}) \
            .eq("id", order["id"]).eq("payment_status", "pending").select("id").execute()
        if not getattr(update, "data", None):
            raise RuntimeError("Order stopped awaiting payment while STK was being started.")
    except Exception:
        log.exception("Could not link STK request to order %s", order["id"])
        raise HTTPException(502, "Could not link the M-Pesa request to this order.")
    return {"status": "success", "checkout_request_id": checkout_id}


@router.post("/mpesa-callback/{secret}")
async def mpesa_callback(secret: str, request: Request):
    # 1) Secret in the URL: random internet traffic can't reach the logic below.
    if not CALLBACK_SECRET or not hmac.compare_digest(secret, CALLBACK_SECRET):
        raise HTTPException(404)

    try:
        data = await request.json()
        cb = data["Body"]["stkCallback"]
        checkout_id = cb["CheckoutRequestID"]
        code = str(cb.get("ResultCode"))
    except Exception:
        return ACK  # malformed: ignore quietly

    try:
        items = (cb.get("CallbackMetadata") or {}).get("Item") or []
        meta = {i.get("Name"): i.get("Value") for i in items if isinstance(i, dict)}
        receipt = meta.get("MpesaReceiptNumber")
        amount = meta.get("Amount")

        # audit trail, idempotent on the UNIQUE checkout_request_id
        supabase.table("mpesa_transactions").upsert({
            "merchant_request_id": cb.get("MerchantRequestID"),
            "checkout_request_id": checkout_id,
            "result_code": int(code) if code.lstrip("-").isdigit() else -1,
            "result_desc": cb.get("ResultDesc"),
            "mpesa_receipt": receipt,
            "amount": amount,
            "phone_number": str(meta.get("PhoneNumber") or ""),
        }, on_conflict="checkout_request_id").execute()

        if code == "0":
            if amount is None or not receipt:
                log.error("Successful callback omitted amount or receipt: %s", checkout_id)
                return ACK
            # 2) Don't trust the POST body alone: a customer knows their own
            #    CheckoutRequestID and could forge this. Ask Daraja directly.
            try:
                q = await DarajaService.query_stk_status(checkout_id)
            except Exception:
                log.exception("STK confirm query failed; leaving order pending")
                return ACK   # customer can use /refresh-payment; no guessing
            if str((q or {}).get("ResultCode", "")) != "0":
                log.warning("Callback said paid but Daraja disagrees: %s", checkout_id)
                return ACK

            # 3) Idempotent, amount-checked update. NO "newest pending order" fallback.
            res = supabase.rpc("mark_order_paid", {
                "p_checkout_id": checkout_id,
                "p_receipt": receipt,
                "p_amount": amount,
            }).execute()
            order = res.data[0] if isinstance(res.data, list) and res.data else res.data
            if not order:
                log.error("Paid callback with no matching order: %s receipt=%s", checkout_id, receipt)
            elif send_order_whatsapp_alert:
                try:
                    await send_order_whatsapp_alert(order, receipt)
                except Exception:
                    log.exception("WhatsApp alert failed")
        else:
            row = supabase.table("orders").select("id").eq("checkout_request_id", checkout_id) \
                .limit(1).execute().data or []
            if row:
                new_status = "Cancelled" if code == "1032" else "Payment Failed"
                supabase.rpc("release_order_stock",
                             {"p_order_id": row[0]["id"], "p_new_status": new_status}).execute()
    except Exception as e:
        # 'amount_mismatch' lands here too: log loudly, never mark paid
        log.exception("Callback processing error for %s: %s", checkout_id, e)

    return ACK  # always 200 so Safaricom doesn't hammer retries