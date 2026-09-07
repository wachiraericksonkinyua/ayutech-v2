import os
import json
import re
import urllib.parse
import httpx
import ast
from app.db.supabase_client import supabase

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/"

def build_github_image_url(relative_path: str) -> str:
    if not relative_path:
        return ""
    cleaned_path = relative_path.replace("\\", "/").strip()
    encoded_path = urllib.parse.quote(cleaned_path)
    return f"{GITHUB_RAW_BASE}{encoded_path}"

def parse_js_array_to_list(js_content: str) -> list:
    """Strips non-printable U+00A0 characters and parses JS arrays safely."""
    try:
        # 1. Clean invisible non-breaking spaces (U+00A0)
        clean_content = js_content.replace('\xa0', ' ').replace('\u00a0', ' ')

        # 2. Extract array content inside [...]
        match = re.search(r'\[.*\]', clean_content, re.DOTALL)
        if not match:
            return []
        array_str = match.group(0)

        # 3. Strip JS single-line and multi-line comments
        array_str = re.sub(r'//.*?\n', '\n', array_str)
        array_str = re.sub(r'/\*.*?\*/', '', array_str, flags=re.DOTALL)

        # 4. Quote unquoted dictionary keys (e.g. id:, name:, priceCents:)
        array_str = re.sub(r'(\b[a-zA-Z_]\w*\b)\s*:', r'"\1":', array_str)

        # 5. Map JS booleans and null to Python equivalents
        array_str = re.sub(r'\btrue\b', 'True', array_str)
        array_str = re.sub(r'\bfalse\b', 'False', array_str)
        array_str = re.sub(r'\bnull\b', 'None', array_str)

        # 6. Remove trailing commas
        array_str = re.sub(r',\s*([\]}])', r'\1', array_str)

        return ast.literal_eval(array_str)
    except Exception as e:
        print(f"⚠️ Parsing Error: {e}")
        return []

def seed_all_categories_from_github():
    data_files = {
        "bodyparts.js": "Body Parts",
        "brakeparts.js": "Brake Parts",
        "engineparts.js": "Engine Parts",
        "gearparts.js": "Gear Parts",
        "lubricants.js": "Lubricants",
        "serviceparts.js": "Service Parts",
        "suspensionparts.js": "Suspension Parts"
    }

    total_seeded = 0

    with httpx.Client(timeout=15.0) as client:
        for filename, category_name in data_files.items():
            raw_url = f"{GITHUB_RAW_BASE}data/{filename}"
            print(f"\n🌐 Fetching {category_name} from GitHub ({raw_url})...")

            try:
                res = client.get(raw_url)
                if res.status_code != 200:
                    print(f"  ❌ Failed to download {filename} (HTTP {res.status_code})")
                    continue

                items = parse_js_array_to_list(res.text)
                print(f"  📦 Parsed {len(items)} items from {filename}")

                for item in items:
                    if not isinstance(item, dict):
                        continue
                        
                    p_name = str(item.get("name", "")).strip()
                    if not p_name:
                        continue

                    raw_img = str(item.get("image", ""))
                    img_url = build_github_image_url(raw_img) if raw_img else ""
                    
                    raw_price = item.get("priceCents", item.get("price", 0))
                    price = float(raw_price) if raw_price else 0.0

                    payload = {
                        "name": p_name,
                        "category": category_name,
                        "price": price,
                        "stock_quantity": 10,
                        "image_url": img_url
                    }

                    try:
                        supabase.table("products").insert(payload).execute()
                        total_seeded += 1
                        print(f"    ✅ Inserted: {p_name} | KES {price:,.2f}")
                    except Exception as db_err:
                        print(f"    ⚠️ DB Insert Error on '{p_name}': {db_err}")

            except Exception as req_err:
                print(f"  ❌ Network Error: {req_err}")

    print(f"\n🎉 ALL CATEGORIES SEEDED! Total Products Added: {total_seeded}")

if __name__ == "__main__":
    seed_all_categories_from_github()