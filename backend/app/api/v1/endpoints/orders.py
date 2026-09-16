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

        if "M-Pesa" in payload.payment_method:
            daraja = DarajaService()
            stk_res = await daraja.send_stk_push(
                phone_number=payload.phone,
                amount=int(payload.total),
                account_reference=short_ref,
                transaction_desc="Auto Parts Order"
            )
            checkout_request_id = stk_res.get("CheckoutRequestID", "")

        order_record = {
            "id": order_uuid,
            "order_reference": short_ref,
            "checkout_request_id": checkout_request_id,
            "customer_id": payload.customer_id,
            "customer_phone": payload.phone,
            "phone": payload.phone,
            "fulfillment": payload.fulfillment,
            "location": payload.location,
            "payment_method": payload.payment_method,
            "total": payload.total,
            "total_amount": payload.total,
            "status": "Pending PIN" if "M-Pesa" in payload.payment_method else "Processing",
            "items": [item.dict() for item in payload.items]
        }

        try:
            supabase.table("orders").insert(order_record).execute()
        except Exception as db_err:
            print(f"Supabase DB insert error: {db_err}")

        return {
            "status": "success",
            "message": "STK prompt sent to phone",
            "order_id": short_ref,
            "checkout_request_id": checkout_request_id
        }

    except Exception as e:
        print(f"Checkout exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{order_ref}")
async def get_order_status(order_ref: str):
    try:
        res = supabase.table("orders").select("status, receipt_number").eq("order_reference", order_ref).execute()
        data = res.data if hasattr(res, "data") else []
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            record = data[0]
            return {
                "status": record.get("status", "Pending PIN"),
                "receipt_number": record.get("receipt_number", "")
            }
    except Exception as e:
        print(f"Status check error: {e}")
    return {"status": "Pending PIN", "receipt_number": ""}

@router.get("/user/{customer_id}")
async def get_user_orders(customer_id: str):
    try:
        res = supabase.table("orders").select("*").eq("customer_id", customer_id).order("total", desc=True).execute()
        orders_list = res.data if hasattr(res, "data") else []
        return {"status": "success", "orders": orders_list}
    except Exception as e:
        print(f"Fetch user orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-receipt")
async def verify_receipt(payload: VerifyReceiptRequest):
    order_ref = payload.order_reference.strip()

    try:
        res = supabase.table("orders").select("*").eq("order_reference", order_ref).execute()
        data = getattr(res, "data", None)

        if not isinstance(data, list) or not data:
            raise HTTPException(status_code=400, detail="Order reference not found.")

        first_record = data[0]
        if not isinstance(first_record, dict):
            raise HTTPException(status_code=400, detail="Order record is invalid.")

        order_status = first_record.get("status")
        if order_status in ["Paid", "Fulfilled"]:
            return {"status": "success", "message": "Order is already verified as Paid!"}

        raise HTTPException(status_code=400, detail="Payment not detected on M-Pesa network yet.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))