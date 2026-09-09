# backend/app/services/ai_engine.py

import os
import json
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.db.supabase_client import supabase

DELIVERY_RATES = {
    "machakos": 400,
    "thika": 300,
    "kiambu": 300,
    "nakuru": 600,
    "mombasa": 800,
    "eldoret": 700,
    "kisumu": 700,
    "nyeri": 400
}

CATALOG_SUMMARY = os.getenv("CATALOG_SUMMARY", "No inventory available.")

SYSTEM_INSTRUCTIONS = f"""
You are the official digital sales assistant for Ayutech Motors on Kirinyaga Road, Nairobi.
Your job is to respond warmly, concisely, and professionally to WhatsApp inquiries.
You are the AyuTech Motors Spare Parts Assistant at Kirinyaga Road, Nairobi.
Specialties: Toyota 1KD, 2KD, 3L, 5L, 7L, 9L engines, Hilux, HiAce, gearboxes, and service parts.
Response Rules:
1. When greeted informally (e.g. 'sasa', 'niaje', 'mambo', 'habari', 'hello'), reply naturally and briefly: "Fit sana! Unatafuta spare gani leo?" or "Hello! What auto part or vehicle model can I help you find today?"
2. Answer fitment, pricing, and stock inquiries in clear, direct English (or Swahili if greeted in Swahili).
3. Maximum 2 short sentences per reply.
4. Reference exact inventory details from the list below when applicable.

Relevant Inventory:
{CATALOG_SUMMARY}
COMMUNICATION STYLE RULES:
1. Maximum length: 2 short sentences.
2. Tone: Warm, polite, and helpful Nairobi business Sheng/Swahili.
3. Keep greetings brief.

DELIVERY RATE RULES:
- Machakos: KES 400 | Thika/Kiambu: KES 300 | Nakuru: KES 600
- Mombasa/Kisumu/Eldoret: KES 800 | Nyeri: KES 400

CRITICAL HANDOFF RULES:
1. If the user confirms they want to speak to or connect with the owner (e.g., "Niko interested", "connect me", "niunganishe", "sawa", "yes"):
   Confirm warmly that you have alerted the owner of Ayutech Motors and they will reach out shortly.
2. If an item is NOT in DATABASE_CONTEXT or out of stock, offer to connect them with the owner to check suppliers.
"""

# ==============================================================================
# 1. TRIAGE BOT & WHATSAPP AUTOMATION
# ==============================================================================

def is_human_takeover_active(customer_phone: str) -> bool:
    try:
        res = supabase.table("leads").select("status").eq("customer_phone", customer_phone).execute()
        if res.data and len(res.data) > 0:
            first = res.data[0]
            status = first.get("status") if isinstance(first, dict) else None
            return status == "human_takeover"
    except Exception as e:
        print(f"⚠️ Human Takeover Check Error: {e}")
    return False

def save_chat_message(customer_phone: str, role: str, content: str):
    try:
        supabase.table("conversations").insert({
            "business_id": "AYUTECH_MAIN",
            "customer_phone": customer_phone,
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"⚠️ Chat Save Error: {e}")

def fetch_recent_chat_history(customer_phone: str, limit: int = 6) -> list:
    try:
        res = supabase.table("conversations")\
            .select("role, content")\
            .eq("customer_phone", customer_phone)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        history = res.data or []
        history.reverse()
        return history
    except Exception as e:
        print(f"⚠️ History Fetch Error: {e}")
        return []

async def query_inventory_db(search_term: str) -> list:
    if not search_term or len(search_term.strip()) < 3 or search_term.lower() in ["unknown", "none"]:
        return []
    try:
        res = supabase.table("products").select("*").ilike("name", f"%{search_term}%").execute()
        return res.data or []
    except Exception as e:
        print(f"⚠️ DB Search Error: {e}")
        return []

def record_out_of_stock_wishlist(part_name: str):
    if not part_name or part_name.lower() in ["none", "unknown", "unspecified"]:
        return
    try:
        clean_part = part_name.strip().title()
        res = supabase.table("stock_wishlist").select("*").eq("part_name", clean_part).execute()
        now_str = datetime.utcnow().isoformat()
        if res.data and len(res.data) > 0:
            first = res.data[0]
            request_count_value = first.get("request_count", 1) if isinstance(first, dict) else 1
            try:
                current_count = int(str(request_count_value))
            except (TypeError, ValueError):
                current_count = 1
            supabase.table("stock_wishlist").update({
                "request_count": current_count + 1,
                "last_requested_at": now_str
            }).eq("part_name", clean_part).execute()
        else:
            supabase.table("stock_wishlist").insert({
                "part_name": clean_part,
                "request_count": 1,
                "last_requested_at": now_str
            }).execute()
        print(f"📈 Stock Wishlist Updated: '{clean_part}'")
    except Exception as e:
        print(f"⚠️ Wishlist Tracking Error: {e}")

def upsert_qualified_lead(customer_phone: str, notes: str, intent_level: str):
    try:
        res = supabase.table("leads").select("*").eq("customer_phone", customer_phone).execute()
        lead_data = {
            "business_id": "AYUTECH_MAIN",
            "customer_phone": customer_phone,
            "intent": intent_level,
            "notes": notes,
            "status": "pending_contact",
            "created_at": datetime.utcnow().isoformat()
        }
        if res.data and len(res.data) > 0:
            first = res.data[0]
            lead_id = first.get("id") if isinstance(first, dict) else None
            if lead_id:
                supabase.table("leads").update(lead_data).eq("id", lead_id).execute()
        else:
            supabase.table("leads").insert(lead_data).execute()
        print(f"🎯 Lead Updated: {customer_phone} ({intent_level})")
    except Exception as e:
        print(f"⚠️ Lead Upsert Error: {e}")

async def extract_context_entities(user_message: str, chat_history: list, groq_key: str) -> dict:
    context_str = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history])
    extraction_prompt = f"""
Analyze conversation history and current message:

RECENT HISTORY:
{context_str}

CURRENT MESSAGE:
"{user_message}"

Extract details into strict JSON:
{{
  "part_name": "overall spare part discussed or 'Unknown'",
  "customer_wants_owner_contact": true/false,
  "intent": "cold, warm, or hot"
}}
Rules:
- set customer_wants_owner_contact to true if user says yes, e.g., "niko interested", "connect me", "niunganishe", "sawa", "yes".
- intent is 'hot' if asking to buy, pay, or requesting owner callback.
ONLY return valid JSON. No markdown wrappers.
"""
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": extraction_prompt}],
        "temperature": 0.0
    }
    groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(groq_endpoint, json=payload, headers=headers, timeout=10.0)
            if res.status_code == 200:
                raw_text = res.json()["choices"][0]["message"]["content"].strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[1].rsplit("\n", 1)[0].replace("json", "").strip()
                return json.loads(raw_text)
        except Exception as e:
            print(f"⚠️ Extraction Warning: {e}")
            
    return {"part_name": "Unknown", "customer_wants_owner_contact": False, "intent": "warm"}

async def generate_grounded_reply(customer_phone: str, user_message: str, image_description: str = "") -> str:
    if is_human_takeover_active(customer_phone):
        print(f"⏸️ AI Bot Paused for {customer_phone}: Human Agent Active.")
        save_chat_message(customer_phone, "user", user_message)
        return ""

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    chat_history = fetch_recent_chat_history(customer_phone, limit=6)
    save_chat_message(customer_phone, "user", user_message)

    entities = await extract_context_entities(user_message, chat_history, groq_key)
    part_name = image_description if image_description else entities.get("part_name", "Unknown")
    wants_owner = entities.get("customer_wants_owner_contact", False)
    intent_level = entities.get("intent", "warm")

    db_items = await query_inventory_db(part_name)

    if wants_owner or intent_level == "hot":
        upsert_qualified_lead(customer_phone, f"Part Requested: {part_name} | Full Request: {user_message}", "hot" if wants_owner else intent_level)

    if not db_items and part_name not in ["Unknown", "None"]:
        record_out_of_stock_wishlist(part_name)

    messages_payload = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
    for msg in chat_history:
        messages_payload.append({"role": msg["role"], "content": msg["content"]})

    context_str = json.dumps(db_items, indent=2) if db_items else "No matching items in database."
    prompt_with_context = (
        f"DELIVERY_RATES_MATRIX:\n{json.dumps(DELIVERY_RATES, indent=2)}\n\n"
        f"DATABASE_CONTEXT:\n{context_str}\n\n"
        f"IMAGE_VISION_ANALYSIS: {image_description if image_description else 'None'}\n"
        f"CUSTOMER_MESSAGE: {user_message}"
    )
    messages_payload.append({"role": "user", "content": prompt_with_context})

    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages_payload,
        "temperature": 0.2
    }

    groq_endpoint = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
    reply = "Mambo! Nimemjulisha owner wa Ayutech Motors. Akutafutia hii part na atakujibu hivi karibuni!"

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(groq_endpoint, json=payload, headers=headers, timeout=20.0)
            if res.status_code == 200:
                reply = res.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"⚠️ Reply API Error ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"⚠️ Reply Generation Error: {e}")

    save_chat_message(customer_phone, "assistant", reply)
    return reply

# ==============================================================================
# 2. IN-APP MOBILE AI ASSISTANT SERVICE
# ==============================================================================

async def generate_fitment_response(messages: list) -> dict:
    if not messages:
        return {"reply": "Please ask a question about our spare parts.", "products": []}

    latest_user_query = messages[-1].get("content", "").lower().strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    matched_products = []
    matched_lines = []
    try:
        res = supabase.table("products").select("id, name, category, price, stock_quantity, image_url").execute()
        all_products = getattr(res, "data", []) or []
        
        q_lower = latest_user_query.lower()
        search_terms = [w for w in q_lower.split() if len(w) > 2]
        
        if "frontlight" in q_lower or "front light" in q_lower:
            search_terms.extend(["front", "light"])
        if "gearbox" in q_lower:
            search_terms.append("gear box")

        for p in all_products:
            p_name = str(p.get("name", "")).lower()
            p_cat = str(p.get("category", "")).lower()
            
            score = sum(1 for term in search_terms if term in p_name or term in p_cat)
            if score > 0 or any(part in p_name for part in ["7l", "1kd", "2kd", "hiace"] if part in q_lower):
                matched_products.append(p)
                matched_lines.append(
                    f"- {p.get('name')}: KES {float(p.get('price', 0)):,.0f} ({p.get('stock_quantity', 0)} in stock)"
                )

        if not matched_lines:
            matched_lines = [
                f"- {p.get('name')}: KES {float(p.get('price', 0)):,.0f} ({p.get('stock_quantity', 0)} in stock)"
                for p in all_products[:8]
            ]
        catalog_summary = "\n".join(matched_lines[:10])
    except Exception as e:
        print(f"Catalog sync error: {e}")
        catalog_summary = "Inventory syncing."

    system_prompt = f"""You are the AyuTech Motors Spare Parts Assistant at Kirinyaga Road, Nairobi.
Specialties: Toyota 1KD, 2KD, 3L, 5L, 7L, 9L engines, Hilux, HiAce, gearboxes, and service parts.

Response Rules:
1. When greeted informally (e.g. 'sasa', 'niaje', 'mambo', 'habari', 'hello'), reply naturally and briefly: "Fit sana! Unatafuta spare gani leo?" or "Hello! What auto part or vehicle model can I help you find today?"
2. Answer fitment, pricing, and stock inquiries in clear, direct English (or Swahili if greeted in Swahili).
3. Maximum 2 short sentences per reply.
4. Reference exact inventory details from the list below when applicable.

Relevant Inventory:
{catalog_summary}
"""

    groq_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages[-3:]:
        groq_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    reply_text = f"We have genuine auto parts in stock at Kirinyaga Road. For '{latest_user_query}', please check our Browse tab or speak with the store directly."

    if groq_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": groq_messages,
                        "max_tokens": 100,
                        "temperature": 0.2
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    if content and content.strip():
                        reply_text = content.strip()
        except Exception as err:
            print(f"Groq request error: {err}")

    # Return top matching products max for instant add-to-cart buttons
    return {
        "reply": reply_text,
        "products": matched_products[:4]
    }