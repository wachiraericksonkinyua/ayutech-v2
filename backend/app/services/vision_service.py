import httpx
import base64
import os
import uuid
from app.db.supabase_client import supabase

async def get_whatsapp_media_url(media_id: str, whatsapp_token: str) -> str:
    """Fetch temporary media download URL from Meta Graph API."""
    url = f"https://graph.facebook.com/v20.0/{media_id}"
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get("url", "")
        print(f"❌ Failed to get Meta media URL: {res.text}")
        return ""


async def get_active_openrouter_vision_model(openrouter_key: str) -> str:
    """Dynamically fetches active free generative vision models from OpenRouter, skipping moderation models."""
    headers = {"Authorization": f"Bearer {openrouter_key}"}
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=10.0)
            if res.status_code == 200:
                models = res.json().get("data", [])
                for model in models:
                    model_id = model.get("id", "").lower()
                    
                    # Skip moderation, guard, or safety models
                    if any(bad_kw in model_id for bad_kw in ["safety", "guard", "moderation"]):
                        continue
                        
                    if model_id.endswith(":free"):
                        architecture = model.get("architecture", {})
                        modality = architecture.get("modality", "")
                        input_modalities = model.get("input_modalities", [])
                        
                        # Match generative vision models
                        if "image" in modality or "image" in input_modalities or any(v in model_id for v in ["vl", "vision", "flash", "llama-3.2"]):
                            print(f"✅ Dynamically discovered active free vision model: {model.get('id')}")
                            return model.get("id")
        except Exception as e:
            print(f"⚠️ Failed to query OpenRouter model list: {e}")
            
    return "meta-llama/llama-3.2-11b-vision-instruct:free"


async def describe_part_image(media_id_or_url: str, whatsapp_token: str, groq_api_key: str = "") -> str:
    """Uploads image to Supabase and identifies spare parts using dynamically selected vision models."""
    if not media_id_or_url:
        return "An image was attached, but media ID/URL could not be retrieved."

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not openrouter_key:
        print("⚠️ OPENROUTER_API_KEY missing in .env")
        return "An image was attached, but vision service is unconfigured."

    # 1. Resolve Meta Media ID
    if not media_id_or_url.startswith("http"):
        download_url = await get_whatsapp_media_url(media_id_or_url, whatsapp_token)
    else:
        download_url = media_id_or_url

    if not download_url:
        print("❌ Could not resolve Meta media download URL.")
        return "An image was attached, but media URL resolution failed."

    # 2. Download binary image bytes from Meta
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        img_res = await client.get(download_url, headers=headers)
        if img_res.status_code != 200:
            print(f"❌ Binary download failed with status: {img_res.status_code}")
            return "An image was attached, but binary download failed."
        
        image_bytes = img_res.content
        content_type = img_res.headers.get("content-type", "image/jpeg")
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{content_type};base64,{base64_img}"

    # 3. Upload bytes to Supabase Storage bucket 'chat_image'
    filename = f"part_{uuid.uuid4().hex[:8]}.jpg"
    try:
        supabase.storage.from_("chat_image").upload(
            file=image_bytes,
            path=filename,
            file_options={"content-type": "image/jpeg"}
        )
        public_url = supabase.storage.from_("chat_image").get_public_url(filename)
        print(f"✅ Image uploaded to Supabase: {public_url}")
    except Exception as upload_err:
        print(f"⚠️ Supabase upload warning: {upload_err}")

    # 4. Query OpenRouter dynamically for active model ID
    active_model = await get_active_openrouter_vision_model(openrouter_key)

    prompt_text = (
        "You are an expert auto spare parts specialist at Ayutech Motors on Kirinyaga Road, Nairobi.\n"
        "Analyze this image carefully and identify the exact automotive spare part.\n"
        "State the exact part name clearly (e.g., 'Front Shock Absorber', 'Spare Wheel Rim / Space Saver', 'Brake Disc Rotors').\n"
        "Provide a concise 1 sentence description of the item."
    )

    payload = {
        "model": active_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ]
    }

    headers_or = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers_or, timeout=25.0)
            if res.status_code == 200:
                result = res.json()
                description = result["choices"][0]["message"]["content"]
                print(f"👁️ OpenRouter Vision Success ({active_model}): {description}")
                return description
            else:
                print(f"❌ OpenRouter Error on '{active_model}' ({res.status_code}): {res.text}")
                return "An image of an automotive spare part was attached, but vision failed."
        except Exception as e:
            print(f"❌ Exception in OpenRouter describe_part_image: {e}")
            return "An image of an automotive spare part was attached, but vision failed."