# backend/app/api/v1/endpoints/whatsapp.py

from fastapi import APIRouter, Request, Query, Response
from app.services.whatsapp import send_whatsapp_message, WHATSAPP_TOKEN
from app.services.vision_service import get_whatsapp_media_url
from app.services.triage import run_triage

router = APIRouter()

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_token == "ayutech_verify_token":
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)

@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Inbound WhatsApp messages -> AI triage bot (3 stages) -> reply to customer."""
    data = await request.json()

    try:
        entry = (data.get("entry") or [{}])[0]
        changes = (entry.get("changes") or [{}])[0]
        value = changes.get("value") or {}
        messages = value.get("messages") or []
    except Exception:
        return {"status": "ignored"}

    if not messages:
        return {"status": "ignored"}

    for msg in messages:
        msg_type = msg.get("type", "")
        from_phone = (msg.get("from") or "").strip().replace("+", "")
        text_body = ""
        image_url = ""

        if msg_type == "text":
            text_body = (msg.get("text") or {}).get("body", "")
        elif msg_type == "image":
            image = msg.get("image") or {}
            media_id = image.get("id", "")
            text_body = (image.get("caption") or "").strip()
            if media_id:
                image_url = await get_whatsapp_media_url(media_id, WHATSAPP_TOKEN)

        if not text_body and not image_url:
            return {"status": "ignored"}

        if not from_phone:
            return {"status": "ignored"}

        try:
            result = await run_triage(
                message=text_body or ("[Image attached - identify and respond to the part in this photo]" if image_url else ""),
                customer_phone=from_phone,
                image_url=image_url,
                source="whatsapp",
            )

            reply = result.get("reply", "")
            if reply:
                await send_whatsapp_message(from_phone, reply)
                print(f"🤖 Triage reply -> {from_phone}")
        except Exception as e:
            print(f"⚠️ WhatsApp triage error for {from_phone}: {e}")
            await send_whatsapp_message(
                from_phone,
                "Habari! Nimekupokea — anayeshughulikia ataweza kukujibu hivi karibuni. Asante kwa kutusubiri!",
            )

    return {"status": "success"}