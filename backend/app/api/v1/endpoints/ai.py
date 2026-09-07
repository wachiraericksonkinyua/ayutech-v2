# backend/app/api/v1/endpoints/ai.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from app.services.ai_engine import generate_fitment_response

router = APIRouter()

class ChatHistoryRequest(BaseModel):
    messages: List[Dict[str, str]]

@router.post("/chat")
async def ai_spare_parts_chat(payload: ChatHistoryRequest):
    if not payload.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")
    
    result = await generate_fitment_response(payload.messages)
    return result