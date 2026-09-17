# backend/app/services/triage.py
# 3-Stage AI Triage Bot for AyuTech Motors
#   Stage 1: Cleaner / Preprocessor   (fast, cheap, near-zero latency)
#   Stage 2: Classifier & Lead Scorer (strict structured JSON)
#   Stage 3: Conversational Responder (empathetic, context-aware, grounded in catalog)
# Vision: Groq llama-3.2-11b-vision-preview primary, OpenRouter free vision fallback.

import os
import re
import json
import httpx
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from app.db.supabase_client import supabase
from app.services.ai_engine import (
    is_human_takeover_active,
    save_chat_message,
    fetch_recent_chat_history,
    query_inventory_db,
    upsert_qualified_lead,
    DELIVERY_RATES,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "qwen/qwen3.8-27b").strip()
VISION_MODEL = os.getenv("VISION_MODEL", "llama-3.2-11b-vision-preview").strip()

VEHICLE_KEYWORDS = [
    "hilux", "hiace", "prado", "landcruiser", "corolla", "noah",
    "vitz", "rav4", "passo", "fortuner", "toyota", "nissan", "mitsubishi",
    "1kd", "2kd", "3l", "5l", "7l", "9l", "1kz", "2l", "3c",
]

PART_LEXICON = [
    "clutch", "brake", "pad", "disc", "rotor", "gearbox", "gear box",
    "shock", "absorber", "filter", "oil filter", "air filter", "bearing",
    "radiator", "alternator", "starter", "battery", "headlight", "frontlight",
    "rear", "mirror", "bumper", "fender", "wheel", "rim", "tyre", "tire",
    "gasket", "seal", "piston", "ring", "injector", "turbo", "camshaft",
    "crankshaft", "timing", "belt", "chain", "water pump", "fuel pump",
    "condenser", "ac compressor", "drive shaft", "propshaft", "differential",
    "knuckle", "ball joint", "tie rod", "shutter", "grill", "bonnet", "boot",
]

SWAHILI_GREETINGS = [
    "sasa", "niaje", "mambo", "habari", "hello", "hi ", "hey", "jambo",
    "vipi", "mzima", "mambo vipi", "poa", "niaje",
]

SPAM_SIGNALS = [
    "free money", "lottery", "win prize", "bitcoin", "cryptocurrency",
    "loan", "wagering", "casino", "buy followers", "http", "www.",
    "click here", "make money fast",
]

# ==============================================================================
# STAGE 1 - CLEANER / PREPROCESSOR  (rule-based first, LLM only when noisy)
# ==============================================================================

def _normalize_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 9:
        if digits.startswith("0"):
            digits = "254" + digits[1:]
        elif digits.startswith("7") or digits.startswith("1"):
            digits = "254" + digits
        elif not digits.startswith("254"):
            digits = "254" + digits
        return digits
    return ""

def _extract_entities(raw: str) -> dict:
    entities = {"phone": "", "prices": [], "parts": [], "vehicles": [], "greeting": False}
    lowered = raw.lower()

    phone_matches = re.findall(r"(?:\+?\s?254|0)?[\s-]?[17]\d{2}[\s-]?\d{3}[\s-]?\d{3}", raw)
    if phone_matches:
        entities["phone"] = _normalize_phone(phone_matches[0])

    entities["prices"] = re.findall(r"(?:KES|Ksh|Ksh\.?|ksh|KSH)\s?([\d,]{3,})", raw)
    entities["prices"] += re.findall(r"\b([\d,]{3,})\s*(?:/|-|per|only)\b", raw)

    for part in PART_LEXICON:
        if part in lowered:
            entities["parts"].append(part)
    for veh in VEHICLE_KEYWORDS:
        if veh in lowered:
            entities["vehicles"].append(veh)

    for g in SWAHILI_GREETINGS:
        pat = re.escape(g).replace(r"\ ", r"\s+")
        if re.search(rf"(^|\b){pat}(\b|$)", lowered):
            entities["greeting"] = True
            break

    entities["parts"] = list(dict.fromkeys(entities["parts"]))
    entities["vehicles"] = list(dict.fromkeys(entities["vehicles"]))
    return entities

def _clean_text(raw: str) -> str:
    text = raw.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"https?://\S+", " [link] ", text)
    text = re.sub(r"!+", "!", text)
    text = re.sub(r"\?+", "?", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]

def _is_noisy(text: str) -> bool:
    if not text:
        return False
    alpha = len(re.findall(r"[a-zA-Z]", text))
    others = len(re.sub(r"[a-zA-Z\s.,!?]", "", text))
    return (others / max(len(text), 1)) > 0.35

async def _llm_deep_clean(text: str, entities: dict) -> str:
    """Cheap LLM normalization only for very noisy/garbled input."""
    if not _is_noisy(text) or not GROQ_KEY:
        return text
    prompt = (
        "Clean this auto-parts customer message: fix typos, expand slang (Sheng/Swahili to plain "
        f"English), remove spam. Return ONLY the cleaned text.\nMESSAGE: \"{text}\"\n"
        f"KNOWN CONTEXT: parts={entities['parts']}, vehicles={entities['vehicles']}"
    )
    payload = {
        "model": TRIAGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 160,
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(GROQ_URL, json=payload,
                                    headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=8.0)
            if res.status_code == 200:
                cleaned = res.json()["choices"][0]["message"]["content"].strip()
                if cleaned and len(cleaned) < 400:
                    return cleaned
    except Exception as e:
        print(f"⚠️ Stage1 LLM clean fallback to raw: {e}")
    return text

async def stage1_clean(message: str) -> dict:
    raw = (message or "").strip()
    entities = _extract_entities(raw)
    cleaned = await _llm_deep_clean(raw, entities)
    return {"raw": raw, "cleaned_text": cleaned, "entities": entities}


# ==============================================================================
# STAGE 2 - CLASSIFIER & LEAD SCORER  (strict JSON, cheap model)
# ==============================================================================

CLASSIFY_SYSTEM = """You are the AyuTech Motors conversion classifier. You classify ONE customer
message from an auto spare parts store (Nairobi, Toyota 1KD/2KD/3L/5L/7L/9L, Hilux/HiAce).
Respond with ONLY a single JSON object, no markdown, no extra text.

Schema (all fields required):
{
  "intent": "lead" | "browse" | "support" | "spam" | "unknown",
  "lead_score": 1-10,
  "urgency": "low" | "medium" | "high",
  "buyer_ready": true|false,
  "wants_owner_contact": true|false,
  "tags": ["part_request","price_check","fitment","stock","delivery","payment","booking","complaint","greeting","owner_connect","other"],
  "route": "sales" | "catalog" | "support" | "canned" | "block",
  "tone": "consultative" | "helpful" | "brief" | "warm_greet" | "blocked",
  "summary": "one-line plain summary of what the user needs"
}

Rules:
- intent "lead": asking to buy, price, pay, place order, wants owner/booking, ready to purchase.
- intent "browse": just looking, asking what's available or for a catalog.
- intent "support": complaint, delivery question, order status, damaged part, returns.
- intent "spam": unsolicited promotions, links, lottery, off-topic bulk text.
- lead_score: 1-3 cold/looking, 4-6 interested+naming a part, 7-8 price+stock asked, 9-10 wants to pay/order/owner callback.
- route "sales": high-value or owner connection needed; "catalog": show product matches;
  "support": helpdesk answers; "canned": greeting or trivial message; "block": spam.
- Greetings alone => intent "browse", lead_score 1-2, route "canned", tone "warm_greet".
- Owner phrases "niko interested / niunganishe / connect me / owner / yes" => wants_owner_contact true, tone "consultative".
"""

async def _groq_json(messages: list, temperature: float = 0.0, format_json: bool = True) -> Optional[dict]:
    if not GROQ_KEY:
        return None
    payload = {
        "model": TRIAGE_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 300,
    }
    if format_json:
        payload["response_format"] = {"type": "json_object"}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(GROQ_URL, json=payload,
                                    headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=15.0)
            if res.status_code != 200:
                print(f"⚠️ Groq classify status {res.status_code}: {res.text[:200]}")
                return None
            content = res.json()["choices"][0]["message"]["content"].strip()
            return _robust_json(content)
    except Exception as e:
        print(f"⚠️ Groq classify exception: {e}")
        return None

def _robust_json(content: str) -> Optional[dict]:
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("\n", 1)[0].replace("json", "").strip()
    try:
        return json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None

def _is_spam_by_rules(text: str) -> bool:
    lowered = text.lower()
    return any(sig in lowered for sig in SPAM_SIGNALS)

def _default_classification(cleaned: str, entities: dict) -> dict:
    if _is_spam_by_rules(cleaned):
        return {"intent": "spam", "lead_score": 1, "urgency": "low",
                "buyer_ready": False, "wants_owner_contact": False,
                "tags": ["spam"], "route": "block", "tone": "blocked",
                "summary": "Spam or off-topic message."}
    return {"intent": "unknown", "lead_score": 2, "urgency": "low",
            "buyer_ready": False, "wants_owner_contact": False,
            "tags": ["other"], "route": "canned", "tone": "helpful",
            "summary": "Unclassified customer message."}

async def stage2_classify(cleaned: str, entities: dict) -> dict:
    if _is_spam_by_rules(cleaned) or any(sig in cleaned.lower() for sig in SPAM_SIGNALS):
        return _default_classification(cleaned, entities)

    context = {
        "parts": entities["parts"] or [],
        "vehicles": entities["vehicles"] or [],
        "prices_mentioned": entities["prices"],
        "phone_extracted": entities["phone"],
    }
    prompt = (
        f"USER MESSAGE (cleaned): \"{cleaned}\"\n\n"
        f"EXTRACTED ENTITIES: {json.dumps(context)}\n\n"
        "Classify exactly per your JSON schema."
    )
    result = await _groq_json([
        {"role": "system", "content": CLASSIFY_SYSTEM},
        {"role": "user", "content": prompt},
    ])
    if result:
        defaults = _default_classification(cleaned, entities)
        merged = {**defaults, **result}
        merged["tags"] = list(dict.fromkeys(merged.get("tags", [])))
        merged["lead_score"] = max(1, min(10, int(merged.get("lead_score", 2) or 2)))
        return merged

    rule = _rule_score(cleaned, entities)
    if rule:
        return rule
    return _default_classification(cleaned, entities)

def _rule_score(cleaned: str, entities: dict) -> Optional[dict]:
    lowered = cleaned.lower()
    if entities["greeting"] and len(cleaned.split()) <= 6 and not entities["parts"]:
        return {"intent": "browse", "lead_score": 2, "urgency": "low", "buyer_ready": False,
                "wants_owner_contact": False, "tags": ["greeting"], "route": "canned",
                "tone": "warm_greet", "summary": "Greeting only."}
    if entities["parts"]:
        score = 5
        if entities["prices"]:
            score += 2
        if any(w in lowered for w in ["buy", "order", "pay", "price", "cost", "bei", "let me", "take"]):
            score += 2
        if any(w in lowered for w in ["niunganishe", "owner", "interested", "connect", "niko", "kesho"]):
            score += 1
        return {"intent": "lead", "lead_score": min(10, score), "urgency": "medium",
                "buyer_ready": "price" in lowered or "buy" in lowered,
                "wants_owner_contact": any(w in lowered for w in ["niunganishe", "connect", "owner", "interested"]),
                "tags": ["part_request"] + (["price_check"] if entities["prices"] else []),
                "route": "sales", "tone": "consultative",
                "summary": f"Asking about {'/'.join(entities['parts'][:2])}."}
    if any(w in lowered for w in ["status", "track", "delivery", "where is my", "complaint", "refund", "exchange"]):
        return {"intent": "support", "lead_score": 3, "urgency": "high", "buyer_ready": False,
                "wants_owner_contact": False, "tags": ["delivery", "complaint"],
                "route": "support", "tone": "helpful", "summary": "Support / delivery question."}
    return None


# ==============================================================================
# STAGE 3 - CONVERSATIONAL RESPONDER  (tone by route, grounded in catalog)
# ==============================================================================

def _tone_instruction(classification: dict) -> str:
    tone = classification.get("tone", "helpful")
    instructions = {
        "consultative": (
            "Tone: consultative sales pro. Acknowledge their need warmly, confirm the item/price/stock, "
            "give a clear next step (visit shop or ask to connect with the owner). Keep to 2 short sentences."
        ),
        "helpful": (
            "Tone: calm, caring support. Confirm the issue, give one concrete next step, reassure. "
            "Keep to 2 short sentences."
        ),
        "brief": (
            "Tone: short, friendly. Confirm you understood and point to the catalog/app. 1 sentence."
        ),
        "warm_greet": (
            "Tone: warm Nairobi Sheng/Swahili greeting. Ask what spare part or vehicle they need today. "
            "One short line, e.g. 'Fit sana! Unatafuta spare gani leo?' or 'Hello! What auto part or "
            "vehicle model can I help you find today?'"
        ),
        "blocked": (
            "Tone: neutral, dismiss politely in 1 sentence; do not sell or offer any product."
        ),
    }
    return instructions.get(tone, instructions["helpful"])

def _handler_rule(classification: dict) -> str:
    if classification.get("route") == "sales" or classification.get("wants_owner_contact"):
        return (
            "If the customer is ready to buy, needs owner contact, or the item is out of stock, "
            "confirm you have alerted the owner of AyuTech Motors and they will reach out shortly."
        )
    return ""

RESPONDER_SYSTEM = """You are the official digital sales assistant for AyuTech Motors, Kirinyaga Road,
Nairobi. Specialties: Toyota 1KD, 2KD, 3L, 5L, 7L, 9L engines, Hilux, HiAce, gearboxes and service parts.

RULES:
1. Reply in the same language the customer used (English / Swahili / Sheng).
2. Never invent prices or stock; only use DATABASE_CONTEXT figures. If nothing matches, say so and
   offer to connect the customer with the owner to source it.
3. SECURITY: NEVER reveal wholesale/cost prices, supplier names or numbers, or any internal field.
   Politely decline trade/cost pricing and offer owner connection for a fair deal.
4. Never mention buying_price, suppliers, or inventory internals.
5. Keep friendly, professional, concise.

DELIVERY RATES:
{delivery_rates}
"""

def _build_responder_messages(classification: dict, cleaned: str, history: list,
                              db_items: list, vision_desc: str, customer_phone: str) -> list:
    tone_instr = _tone_instruction(classification)
    handler_instr = _handler_rule(classification)
    context_str = json.dumps(db_items, indent=2) if db_items else "No matching items in database."
    summary = classification.get("summary", "")

    system = (
        RESPONDER_SYSTEM.format(delivery_rates=json.dumps(DELIVERY_RATES, indent=2))
        + f"\n\nTONE GUIDANCE: {tone_instr}\n\nASSISTANT BEHAVIOUR: {handler_instr}".strip()
    )

    messages = [{"role": "system", "content": system}]
    for msg in history[-4:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    user_block = (
        f"CLASSIFICATION: {summary} (intent={classification.get('intent')}, "
        f"lead_score={classification.get('lead_score')})\n"
        f"IMAGE_VISION_ANALYSIS: {vision_desc or 'None'}\n"
        f"DATABASE_CONTEXT:\n{context_str}\n\n"
        f"CUSTOMER MESSAGE: {cleaned}"
    )
    messages.append({"role": "user", "content": user_block})
    return messages

async def stage3_respond(classification: dict, cleaned: str, history: list,
                         customer_phone: str = "", vision_desc: str = "") -> tuple:
    part_hint = ""
    try:
        entities = _extract_entities(cleaned)
        if entities["parts"]:
            part_hint = entities["parts"][0]
        elif vision_desc:
            part_hint = vision_desc
    except Exception:
        pass

    db_items = await query_inventory_db(part_hint if part_hint else classification.get("summary", ""))

    fallback_reply = "Karibu AyuTech Motors! Nimeelewa ombi lako — unatafuta seti gani / ni gari gani? DM tukiendelea."
    messages = _build_responder_messages(classification, cleaned, history, db_items, vision_desc, customer_phone)

    reply = fallback_reply
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                GROQ_URL,
                json={
                    "model": TRIAGE_MODEL,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 160,
                },
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                timeout=20.0,
            )
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"].strip()
                if content:
                    reply = content
            else:
                print(f"⚠️ Stage3 responder status {res.status_code}: {res.text[:160]}")
    except Exception as e:
        print(f"⚠️ Stage3 responder exception: {e}")

    return reply, db_items[:4]


# ==============================================================================
# VISION PREPROCESSING  (Groq primary, OpenRouter fallback)
# ==============================================================================

async def describe_image(image_url: str) -> str:
    """Identifies a spare part from an image URL (http or data URL)."""
    if not image_url:
        return ""
    if GROQ_KEY:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    GROQ_URL,
                    json={
                        "model": VISION_MODEL,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text",
                                 "text": "You are an auto spare parts expert at AyuTech Motors, Nairobi. "
                                         "Identify the exact part, then a one-sentence description. "
                                         "Example: 'Front Shock Absorber - used Toyota Hilux front shock, appears used but intact.'"},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        }],
                        "temperature": 0.0,
                        "max_tokens": 120,
                    },
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    timeout=25.0,
                )
                if res.status_code == 200:
                    desc = res.json()["choices"][0]["message"]["content"].strip()
                    print(f"👁️ Groq Vision ({VISION_MODEL}): {desc[:120]}")
                    return desc
                print(f"⚠️ Groq vision status {res.status_code}: {res.text[:160]}")
        except Exception as e:
            print(f"⚠️ Groq vision exception: {e}")
    return await _openrouter_vision_fallback(image_url)

async def _openrouter_vision_fallback(image_url: str) -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return ""
    try:
        from app.services.vision_service import get_active_openrouter_vision_model
        model = await get_active_openrouter_vision_model(key)
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text",
                             "text": "Identify the exact automotive spare part and give a one-sentence description."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }],
                },
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=25.0,
            )
            if res.status_code == 200:
                desc = res.json()["choices"][0]["message"]["content"].strip()
                print(f"👁️ OpenRouter Vision ({model}): {desc[:120]}")
                return desc
    except Exception as e:
        print(f"⚠️ OpenRouter vision exception: {e}")
    return ""


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================

LEAD_INTENTS = ("lead",)
LEAD_MIN_SCORE = 6

async def run_triage(message: str, customer_phone: str = "", image_url: str = "",
                     chat_history: Optional[list] = None, source: str = "app") -> dict:
    if source == "whatsapp" and is_human_takeover_active(customer_phone):
        return {"status": "human_takeover", "reply": "", "note": "Human agent active; AI paused."}

    history = chat_history if chat_history is not None else (
        fetch_recent_chat_history(customer_phone, limit=6) if customer_phone else []
    )

    stage1 = await stage1_clean(message)
    vision_desc = await describe_image(image_url) if image_url else ""

    stage2 = await stage2_classify(stage1["cleaned_text"], stage1["entities"])

    reply, products = await stage3_respond(
        stage2, stage1["cleaned_text"], history, customer_phone, vision_desc
    )

    if source == "whatsapp" and customer_phone:
        try:
            save_chat_message(customer_phone, "user", message)
            save_chat_message(customer_phone, "assistant", reply)
        except Exception as e:
            print(f"⚠️ Triage conversation save: {e}")

    is_hot_lead = (
        stage2["intent"] in LEAD_INTENTS
        and stage2["lead_score"] >= LEAD_MIN_SCORE
    ) or stage2.get("wants_owner_contact")

    if is_hot_lead and customer_phone:
        try:
            lead_note = json.dumps({
                "part": stage1["entities"]["parts"][:3],
                "vehicle": stage1["entities"]["vehicles"][:2],
                "phone": stage1["entities"]["phone"],
                "lead_score": stage2["lead_score"],
                "tags": stage2["tags"],
                "summary": stage2.get("summary", ""),
                "full": message,
            }, default=str)
            upsert_qualified_lead(customer_phone, lead_note, "hot" if stage2.get("wants_owner_contact") else stage2["intent"])
            print(f"🎯 Triage lead saved: {customer_phone} score={stage2['lead_score']}")
        except Exception as e:
            print(f"⚠️ Triage lead save: {e}")

    return {
        "status": "ok",
        "cleaned_text": stage1["cleaned_text"],
        "entities": stage1["entities"],
        "classification": stage2,
        "vision": vision_desc,
        "reply": reply,
        "products": products,
    }