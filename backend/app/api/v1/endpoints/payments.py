# backend/app/api/v1/endpoints/payments.py

import inspect
from fastapi import APIRouter, HTTPException, Request
from app.db.supabase_client import supabase
from app.services import daraja_service
from app.services.whatsapp import send_order_whatsapp_alert

router = APIRouter()

async def _invoke_daraja_stk(phone_number: str, amount: int, account_reference: str, transaction_desc: str):
    """Finds and executes any sync/async STK push function or class method in daraja_service."""
    candidates = []

    for name in ["initiate_stk_push", "stk_push", "push_stk_push", "trigger_stk_push", "send_stk_push"]:
        fn = getattr(daraja_service, name, None)
        if callable(fn):
            candidates.append(fn)

    for obj_name in ["daraja_service", "daraja_client", "daraja", "DarajaService"]:
        obj = getattr(daraja_service, obj_name, None)
        if obj is not None:
            instance = obj() if inspect.isclass(obj) else obj
            for m_name in ["initiate_stk_push", "stk_push", "push_stk", "trigger_stk"]:
                fn = getattr(instance, m_name, None)
                if callable(fn):
                    candidates.append(fn)

    if not candidates:
        attrs = [a for a in dir(daraja_service) if not a.startswith("__")]
        raise AttributeError(f"No known STK method found. Available exports: {attrs}")

    chosen_fn = candidates[0]
    sig = inspect.signature(chosen_fn)
    kwargs = {}
    for p in sig.parameters.values():
        p_name = p.name.lower()
        if "phone" in p_name:
            kwargs[p.name] = phone_number
        elif "amount" in p_name:
            kwargs[p.name] = amount
        elif "account" in p_name or "reference" in p_name or "ref" in p_name:
            kwargs[p.name] = account_reference
        elif "desc" in p_name:
            kwargs[p.name] = transaction_desc

    if inspect.iscoroutinefunction(chosen_fn):
        return await chosen_fn(**kwargs) if kwargs else await chosen_fn(phone_number, amount, account_reference, transaction_desc)
    else:
        return chosen_fn(**kwargs) if kwargs else chosen_fn(phone_number, amount, account_reference, transaction_desc)


@router.post("/pos-stk-push")
async def trigger_pos_stk_push(payload: dict):
    phone = str(payload.get("phone", "")).strip()
    amount = float(payload.get("amount", 0))
    order_ref = str(payload.get("order_reference", "POS")).strip()
    order_id = payload.get("order_id")

    if not phone or amount <= 0:
        raise HTTPException(status_code=400, detail="Valid phone number and amount required.")

    try:
        stk_response = await _invoke_daraja_stk(
            phone_number=phone,
            amount=int(amount),
            account_reference=order_ref,
            transaction_desc="Counter Sale POS"
        )
        checkout_req_id = stk_response.get("CheckoutRequestID") if isinstance(stk_response, dict) else getattr(stk_response, "CheckoutRequestID", "")

        # Attach CheckoutRequestID to the order in Supabase so the webhook can match it!
        if checkout_req_id:
            update_data = {"checkout_request_id": checkout_req_id}
            if order_id:
                supabase.table("orders").update(update_data).eq("id", order_id).execute()
            elif order_ref and order_ref != "POS":
                # Try matching by receipt_number/ref or order ID
                supabase.table("orders").update(update_data).or_(f"id.eq.{order_ref},receipt_number.ilike.%{order_ref}%").execute()
            else:
                # Fallback: link to the most recent Pending PIN order for this phone
                recent = supabase.table("orders").select("id").eq("customer_phone", phone).eq("status", "Pending PIN").order("created_at", desc=True).limit(1).execute()
                recent_rows = getattr(recent, "data", None) or []
                if recent_rows and isinstance(recent_rows, list) and isinstance(recent_rows[0], dict):
                    recent_id = recent_rows[0].get("id")
                    if recent_id is not None:
                        supabase.table("orders").update(update_data).eq("id", recent_id).execute()

        return {
            "status": "success", 
            "data": stk_response,
            "checkout_request_id": checkout_req_id
        }
    except Exception as e:
        print(f"STK Push error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callback")
@router.post("/mpesa-callback")
async def mpesa_callback(request: Request):
    data = await request.json()
    stk_callback = data.get("Body", {}).get("stkCallback", {})
    result_code = stk_callback.get("ResultCode")
    checkout_request_id = stk_callback.get("CheckoutRequestID")

    print(f"📥 Safaricom Callback: ID={checkout_request_id} | Code={result_code}")

    if result_code == 0:
        meta_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        receipt = next((i.get("Value") for i in meta_items if i.get("Name") == "MpesaReceiptNumber"), "MPESA_PAID")

        # 1. Update order matching checkout_request_id
        db_res = supabase.table("orders").update({
            "status": "Paid",
            "receipt_number": receipt
        }).eq("checkout_request_id", checkout_request_id).execute()

        data_rows = getattr(db_res, "data", []) or []

        # 2. Fallback: if no row had this checkout_request_id, update the most recent Pending PIN order
        if not data_rows:
            pending_res = supabase.table("orders").select("id").eq("status", "Pending PIN").order("created_at", desc=True).limit(1).execute()
            pending_data = getattr(pending_res, "data", None) or []
            if pending_data:
                first_row = pending_data[0]
                if isinstance(first_row, dict) and "id" in first_row:
                    target_id = first_row["id"]
                    supabase.table("orders").update({
                        "status": "Paid",
                        "receipt_number": receipt,
                        "checkout_request_id": checkout_request_id
                    }).eq("id", target_id).execute()
                    print(f"Linked receipt {receipt} to pending order {target_id}")

        print(f"Order Paid! Receipt: {receipt}")