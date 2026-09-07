# backend/app/api/v1/endpoints/whatsapp.py

from fastapi import APIRouter, Request, Query, Response
from app.services.whatsapp import send_whatsapp_message

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
    data = await request.json()
    # Process incoming customer messages if needed
    return {"status": "success"}