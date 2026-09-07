import inspect
import os
from fastapi import APIRouter, HTTPException, Request
from app.core.config import supabase
from app.services import daraja_service
from app.services.whatsapp_service import send_order_whatsapp_alert

router = APIRouter()


async def _invoke_daraja_stk(phone_number: str, amount: int, account_reference: str, transaction_desc: str):
    """Dynamically invoke STK push across different method names in DarajaService."""
    candidates = []
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

        # Attach CheckoutRequestID to the order in Supabase safely (avoiding UUID type mismatch errors)
        if checkout_req_id:
            update_data = {"checkout_request_id": checkout_req_id}
            
            if order_id and len(str(order_id)) > 30:
                try:
                    supabase.table("orders").update(update_data).eq("id", order_id).execute()
                except Exception:
                    pass
            elif order_ref and order_ref != "POS":
                try:
                    supabase.table("orders").update(update_data).ilike("receipt_number", f"%{order_ref}%").execute()
                except Exception:
                    pass
            
            try:
                recent = supabase.table("orders").select("id").eq("customer_phone", phone).eq("status", "Pending PIN").order("created_at", desc=True).limit(1).execute()
                if recent.data:
                    supabase.table("orders").update(update_data).eq("id", recent.data[0]["id"]).execute()
            except Exception as link_err:
                print(f"Fallback link error: {link_err}")

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

        db_res = supabase.table("orders").update({
            "status": "Paid",
            "receipt_number": receipt
        }).eq("checkout_request_id", checkout_request_id).execute()

        data_rows = getattr(db_res, "data", []) or []

        if not data_rows:
            pending_res = supabase.table("orders").select("id").eq("status", "Pending PIN").order("created_at", desc=True).limit(1).execute()
            if pending_res.data:
                target_id = pending_res.data[0]["id"]
                upd_res = supabase.table("orders").update({
                    "status": "Paid",
                    "receipt_number": receipt,
                    "checkout_request_id": checkout_request_id
                }).eq("id", target_id).execute()
                data_rows = getattr(upd_res, "data", []) or []
                print(f"Linked receipt {receipt} to pending order {target_id}")

        print(f"✅ Order Paid! Receipt: {receipt}")

        if data_rows:
            try:
                await send_order_whatsapp_alert(data_rows[0], receipt)
            except Exception as w_err:
                print(f"WhatsApp alert error: {w_err}")

    elif result_code == 1032:
        supabase.table("orders").update({
            "status": "Cancelled"
        }).eq("checkout_request_id", checkout_request_id).execute()
        print("⚠️ Order Cancelled by user.")

    else:
        supabase.table("orders").update({
            "status": "Payment Failed"
        }).eq("checkout_request_id", checkout_request_id).execute()
        print(f"❌ Payment Failed with Code: {result_code}")

    return {"ResultCode": 0, "ResultDesc": "Accepted"}