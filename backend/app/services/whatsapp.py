# backend/app/services/whatsapp.py

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = (
    os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_ID") or ""
).strip()
OWNER_PHONE_NUMBER = os.getenv("OWNER_WHATSAPP_NUMBER", "254112323814").strip().replace("+", "")


async def send_whatsapp_message(to_phone: str, message: str) -> dict:
    """Sends text via Meta WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("⚠️ WhatsApp credentials missing. Message skipped.")
        return {"status": "skipped", "reason": "No credentials"}

    target_phone = to_phone.strip().replace("+", "")
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": target_phone,
        "type": "text",
        "text": {"body": message},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            print(f"📲 WhatsApp Dispatch -> {target_phone} | Status: {res.status_code} | Body: {res.text}")
            return res.json()
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message to {target_phone}: {e}")
        return {"status": "error", "error": str(e)}


async def send_order_whatsapp_alert(order_data: dict, receipt_number: str):
    """Sends formatted order summary to store owner upon successful payment."""
    items = order_data.get("items", []) or []
    items_summary = "\n".join([
        f"• {item.get('name', 'Part')} (x{item.get('qty', 1)}) - KES {float(item.get('price', 0)) * int(item.get('qty', 1)):,.0f}"
        for item in items
    ])

    total_val = float(order_data.get("total_amount") or order_data.get("total") or 0)

    message_text = (
        f"✅ *NEW PAID ORDER - AYUTECH MOTORS*\n\n"
        f"🧾 *Order ID:* {order_data.get('order_reference', 'N/A')}\n"
        f"💳 *M-Pesa Receipt:* {receipt_number}\n"
        f"📞 *Customer Phone:* {order_data.get('customer_phone', 'N/A')}\n"
        f"📦 *Fulfillment:* {order_data.get('fulfillment', 'N/A')}\n"
        f"📍 *Location:* {order_data.get('location', 'Kirinyaga Road Shop')}\n\n"
        f"🛒 *Items:*\n{items_summary}\n\n"
        f"💰 *Total Paid:* KES {total_val:,.0f}"
    )

    return await send_whatsapp_message(OWNER_PHONE_NUMBER, message_text)