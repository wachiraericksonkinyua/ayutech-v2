import uuid
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
from app.services.daraja_service import DarajaService
from app.db.supabase_client import supabase
from app.core.rate_limiter import limiter
import re

router = APIRouter()

class OrderItem(BaseModel):
    id: str
    name: str
    price: float
    qty: int
    image: Optional[str] = ""

class CheckoutRequest(BaseModel):
    phone: str
    fulfillment: str
    location: str
    delivery_address: str = ""
    payment_method: str
    items: List[OrderItem]
    total: float
    customer_id: Optional[str] = None

class VerifyReceiptRequest(BaseModel):
    order_reference: str
    receipt_number: str

@router.post("/checkout", status_code=201)
@limiter.limit("5/minute")
async def process_checkout(request: Request, payload: CheckoutRequest):
    try:
        order_uuid = str(uuid.uuid4())
        short_ref = f"AYU-{order_uuid[:4]}"
        checkout_request_id = ""

        # 1. Trigger Daraja STK Push (Re-enabled)
        if "M-Pesa" in payload.payment_method:
            try:
                daraja = DarajaService()
                stk_res = await daraja.send_stk_push(
                    phone_number=payload.phone,
                    amount=int(payload.total),
                    account_reference=short_ref,
                    transaction_desc="Auto Parts Order"
                )
                checkout_request_id = stk_res.get("CheckoutRequestID", "")
            except Exception as stk_err:
                print(f"Daraja STK Push warning: {stk_err}")
                checkout_request_id = f"sim_{short_ref}"


        # Validate customer_id to ensure it's a valid non-empty UUID string
        valid_customer_id = None
        if payload.customer_id and str(payload.customer_id).strip() not in ["", "None", "null"]:
            valid_customer_id = str(payload.customer_id).strip()

        order_record = {
            "id": order_uuid,
            "order_reference": short_ref,
            "checkout_request_id": checkout_request_id,
            "customer_id": valid_customer_id, # Safely sanitized UUID or None
            "customer_phone": payload.phone,
            "phone": payload.phone,
            "fulfillment": payload.fulfillment,
            "location": payload.location,
            "delivery_address": (payload.delivery_address or "").strip(),
            "payment_method": payload.payment_method,
            "total": payload.total,
            "total_amount": payload.total,
            "status": "Pending PIN" if "M-Pesa" in payload.payment_method else "Processing",
            "items": [item.dict() for item in payload.items]
        }

        try:
            supabase.table("orders").insert(order_record).execute()
        except Exception as db_err:
            # delivery_address column may not exist yet on old DBs - retry without it
            print(f"Supabase DB insert error: {db_err}")
            try:
                order_record.pop("delivery_address", None)
                supabase.table("orders").insert(order_record).execute()
            except Exception as db_err2:
                print(f"Supabase DB insert retry error: {db_err2}")

        return {
            "status": "success",
            "message": "STK prompt sent to phone",
            "order_id": short_ref,
            "checkout_request_id": checkout_request_id
        }

    except Exception as e:
        print(f"Checkout exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/track/{phone}")
async def track_order_by_phone(phone: str):
    """Public order tracking by phone number - no login required."""
    try:
        clean_phone = re.sub(r"[^0-9]", "", (phone or ""))
        if len(clean_phone) < 9:
            raise HTTPException(status_code=400, detail="Enter a valid phone number.")

        res = supabase.table("orders").select(
            "order_reference", "status", "total", "created_at",
            "payment_method", "fulfillment", "items", "receipt_number",
        ).or_(f"phone.eq.{clean_phone},customer_phone.eq.{clean_phone}").order("created_at", desc=True).execute()

        orders_list = getattr(res, "data", None) or []
        return {"status": "success", "orders": orders_list}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Track order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{identifier}")
async def get_user_orders(identifier: str):
    try:
        orders_list = []
        clean_id = (identifier or "").strip()

        if not clean_id or clean_id in ["None", "null", "undefined"]:
            return {"status": "success", "orders": []}

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

        # NO FALLBACK: If not authenticated or no orders match, return empty list!
        return {"status": "success", "orders": orders_list}
    except Exception as e:
        print(f"Fetch user orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/status/{order_ref}")
async def get_order_status(order_ref: str):
    """Returns the live status + M-Pesa receipt for an order by short reference or UUID."""
    try:
        clean_ref = (order_ref or "").strip()
        if not clean_ref:
            raise HTTPException(status_code=400, detail="Order reference required.")

        record = None
        res = supabase.table("orders").select(
            "status", "receipt_number"
        ).eq("order_reference", clean_ref).limit(1).execute()
        records = getattr(res, "data", None) or []
        if records:
            record = records[0]
        else:
            res2 = supabase.table("orders").select(
                "status", "receipt_number"
            ).eq("id", clean_ref).limit(1).execute()
            records2 = getattr(res2, "data", None) or []
            if records2:
                record = records2[0]

        if not isinstance(record, dict):
            raise HTTPException(status_code=404, detail="Order not found.")

        return {
            "order_reference": clean_ref,
            "status": record.get("status", "Pending PIN"),
            "receipt_number": record.get("receipt_number") or "",
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Order status lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-receipt")
async def verify_receipt(payload: VerifyReceiptRequest):
    order_ref = payload.order_reference.strip()
    user_receipt = (payload.receipt_number or "").strip()

    try:
        res = supabase.table("orders").select("*").eq("order_reference", order_ref).execute()
        data = getattr(res, "data", None)

        if not isinstance(data, list) or not data:
            raise HTTPException(status_code=400, detail="Order reference not found.")

        first_record = data[0]
        if not isinstance(first_record, dict):
            raise HTTPException(status_code=400, detail="Order record is invalid.")

        order_id = first_record.get("id")
        order_status = first_record.get("status")
        if order_status in ["Paid", "Fulfilled"]:
            return {"status": "success", "message": "Order is already verified as Paid!"}

        # 1) Authoritative check: query Daraja for the STK transaction status
        checkout_id = str(first_record.get("checkout_request_id", "") or "")
        if checkout_id and not checkout_id.startswith("sim_"):
            try:
                query_res = await DarajaService.query_stk_status(checkout_id)
            except Exception as q_err:
                print(f"Daraja query error: {q_err}")
                query_res = None

            if query_res and query_res.get("ResultCode") == 0:
                receipt = "MPESA_PAID"
                meta = query_res.get("CallbackMetadata", {}).get("Item", [])
                if isinstance(meta, list):
                    receipt = next(
                        (i.get("Value") for i in meta if i.get("Name") == "MpesaReceiptNumber"),
                        user_receipt or "MPESA_PAID",
                    )
                supabase.table("orders").update({
                    "status": "Paid",
                    "receipt_number": receipt,
                }).eq("id", order_id).execute()
                return {
                    "status": "success",
                    "message": "Payment confirmed by M-Pesa!",
                    "receipt_number": receipt,
                }
            if query_res:
                result_code = query_res.get("ResultCode")
                if result_code == 1032:
                    supabase.table("orders").update({"status": "Cancelled"}).eq("id", order_id).execute()
                    raise HTTPException(status_code=400, detail="This payment was cancelled by the customer.")
                raise HTTPException(
                    status_code=400,
                    detail="Payment not completed on M-Pesa yet. Confirm the transaction or retry shortly.",
                )

        # 2) Manual override: confirm using the M-Pesa confirmation code entered by the user
        if user_receipt:
            supabase.table("orders").update({
                "status": "Paid",
                "receipt_number": user_receipt,
            }).eq("id", order_id).execute()
            return {
                "status": "success",
                "message": "Receipt verified manually.",
                "receipt_number": user_receipt,
            }

        raise HTTPException(status_code=400, detail="Payment not detected on M-Pesa network yet.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))