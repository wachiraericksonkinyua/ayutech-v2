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
    customer_id: Optional[str] = None # Added to map orders to the user account

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

        # 1. Trigger Daraja STK Push
        if "M-Pesa" in payload.payment_method:
            daraja = DarajaService()
            stk_res = await daraja.send_stk_push(
                phone_number=payload.phone,
                amount=int(payload.total),
                account_reference=short_ref,
                transaction_desc="Auto Parts Order"
            )
            checkout_request_id = stk_res.get("CheckoutRequestID", "")

        # 2. Match exact Supabase table column names (including total_amount)
        order_record = {
            "id": order_uuid,
            "order_reference": short_ref,
            "checkout_request_id": checkout_request_id,
            "customer_id": payload.customer_id, # Links order directly to the user profile
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
        # Ensure we have a dict-like record before calling .get to avoid attribute errors
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
    """
    Fetch all order history records linked to a specific user UUID.
    """
    try:
        res = supabase.table("orders").select("*").eq("customer_id", customer_id).order("total", desc=True).execute()
        orders_list = res.data if hasattr(res, "data") else []
        return {"status": "success", "orders": orders_list}
    except Exception as e:
        print(f"Fetch user orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-receipt")
async def verify_receipt(payload: VerifyReceiptRequest):
    receipt = payload.receipt_number.strip().upper()
    
    # Strict M-Pesa transaction format check (10 alphanumeric characters)
    if not re.match(r"^[A-Z0-9]{10}$", receipt):
        raise HTTPException(status_code=400, detail="Invalid M-Pesa code format. Must be exactly 10 characters.")
        
    try:
        # Check if this receipt code was already used
        existing = supabase.table("orders").select("id").eq("receipt_number", receipt).execute()
        if existing.data and len(existing.data) > 0:
            raise HTTPException(status_code=400, detail="This M-Pesa receipt has already been used.")

        res = supabase.table("orders").update({
            "status": "Paid",
            "payment_status": "Paid",
            "receipt_number": receipt,
            "mpesa_receipt": receipt
        }).eq("order_reference", payload.order_reference).execute()
        
        return {"status": "success", "message": "Order verified successfully!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# @router.post("/checkout", status_code=201)
# @limiter.limit("5/minute")
# async def process_checkout(request: Request, payload: CheckoutRequest):
#     """
#     Process order checkout with 5 requests/min rate limit.
#     """
#     try:
#         calculated_total = sum(item.qty * item.price for item in payload.items)
#         order_uuid = str(uuid.uuid4())

#         # 1. Insert parent order
#         order_data = {
#             "id": order_uuid,
#             "customer_phone": payload.phone,
#             "total_amount": calculated_total,
#             "status": "pending_payment"
#         }
#         order_res = supabase.table("orders").insert(order_data).execute()
#         if not order_res.data:
#             raise HTTPException(status_code=500, detail="Failed to record order in database")

#         # 2. Insert line items
#         items_payload = [
#             {
#                 "order_id": order_uuid,
#                 "product_id": item.id,
#                 "quantity": item.qty,
#                 "unit_price": item.price
#             }
#             for item in payload.items
#         ]
#         supabase.table("order_items").insert(items_payload).execute()

#         # 3. Trigger Daraja M-Pesa STK Push
#         stk_res = await DarajaService.initiate_stk_push(
#             phone_number=payload.phone,
#             amount=calculated_total,
#             account_reference=order_uuid[:8]
#         )

#         if isinstance(stk_res, dict) and stk_res.get("ResponseCode") == "0":
#             checkout_id = stk_res.get("CheckoutRequestID")

#             supabase.table("orders").update({
#                 "mpesa_checkout_request_id": checkout_id
#             }).eq("id", order_uuid).execute()

#             return {
#                 "status": "success",
#                 "message": "Checkout complete. STK Push sent to phone.",
#                 "order_id": order_uuid,
#                 "checkout_request_id": checkout_id,
#                 "total_amount": calculated_total
#             }
#         else:
#             msg = stk_res.get("CustomerMessage") if isinstance(stk_res, dict) else str(stk_res)
#             supabase.table("orders").update({"status": "payment_failed"}).eq("id", order_uuid).execute()
#             raise HTTPException(status_code=400, detail=msg or "STK Push failed at Daraja")

#     except HTTPException:
#         raise
#     except Exception as e:
#         error_msg = str(e) if str(e) else repr(e)
#         raise HTTPException(status_code=500, detail=error_msg)