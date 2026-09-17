# backend/app/api/v1/endpoints/ai.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.services.ai_engine import generate_fitment_response
from app.services.triage import run_triage

router = APIRouter()

class ChatHistoryRequest(BaseModel):
    messages: List[Dict[str, str]]

class TriageRequest(BaseModel):
    message: str
    customer_phone: str = ""
    image_url: str = ""
    chat_history: Optional[List[Dict[str, str]]] = None
    source: str = "app"

@router.post("/chat")
async def ai_spare_parts_chat(payload: ChatHistoryRequest):
    if not payload.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")

    result = await generate_fitment_response(payload.messages)
    return result

@router.post("/triage")
async def ai_triage(payload: TriageRequest):
    """3-stage AI triage bot: clean -> classify/score -> grounded reply (with optional vision)."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = await run_triage(
        message=payload.message,
        customer_phone=payload.customer_phone,
        image_url=payload.image_url,
        chat_history=payload.chat_history,
        source=payload.source,
    )
    return result