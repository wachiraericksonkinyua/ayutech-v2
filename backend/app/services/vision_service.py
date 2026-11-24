import httpx
import base64
import os
import uuid
from app.db.supabase_client import supabase

OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "",
).strip() or "nvidia/nemotron-3.5-super-vl:free"
MAX_WHATSAPP_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

async def get_whatsapp_media_url(media_id: str, whatsapp_token: str) -> str:
    """Fetch temporary media download URL from Meta Graph API."""
    url = f"https://graph.facebook.com/v20.0/{media_id}"
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get("url", "")
        print(f"❌ Failed to get Meta media URL: {res.text}")
        return ""


async def get_whatsapp_media_data_url(media_id: str, whatsapp_token: str) -> str:
    """Download a Meta-hosted image with its required token for vision APIs."""
    download_url = await get_whatsapp_media_url(media_id, whatsapp_token)
    if not download_url:
        return ""

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            async with client.stream(
                "GET",
                download_url,
                headers={"Authorization": f"Bearer {whatsapp_token}"},
            ) as response:
                if response.status_code != 200:
                    print(f"❌ WhatsApp image download failed: {response.status_code}")
                    return ""

                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                    print(f"❌ Unsupported WhatsApp image type: {content_type}")
                    return ""

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_WHATSAPP_IMAGE_BYTES:
                    print("❌ WhatsApp image exceeds the 5 MB limit.")
                    return ""

                chunks = []
                total_bytes = 0
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > MAX_WHATSAPP_IMAGE_BYTES:
                        print("❌ WhatsApp image exceeds the 5 MB limit.")
                        return ""
                    chunks.append(chunk)

        encoded = base64.b64encode(b"".join(chunks)).decode("ascii")
        return f"data:{content_type};base64,{encoded}"
    except (httpx.HTTPError, ValueError) as exc:
        print(f"❌ WhatsApp image download error: {exc}")
        return ""


def get_openrouter_vision_model() -> str:
    return OPENROUTER_VISION_MODEL


async def describe_part_image(media_id_or_url: str, whatsapp_token: str, groq_api_key: str = "") -> str:
    """Uploads image to Supabase and identifies spare parts with OpenRouter vision."""
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

    # 4. Use the configured OpenRouter vision model
    active_model = get_openrouter_vision_model()

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