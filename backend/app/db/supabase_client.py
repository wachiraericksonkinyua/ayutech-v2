import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load variables from .env file
load_dotenv()

supabase_url: str = os.getenv("SUPABASE_URL", "")
supabase_key: str = os.getenv("SUPABASE_KEY", "")

if not supabase_url or not supabase_key:
    raise ValueError("Missing Supabase URL or Key in environment variables.")

# Public/publishable client - respects Row Level Security.
supabase: Client = create_client(supabase_url, supabase_key)

# Server-only privileged client (service-role / secret key). Admin endpoints
# depend on it to enforce server-side authorization and bypass database RLS.
# NEVER expose this key to any client application.
supabase_secret_key = (
    os.getenv("SUPABASE_SECRET_KEY", "")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
).strip()
if not supabase_secret_key:
    raise ValueError(
        "Missing SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY); "
        "the API requires a server-side service-role key."
    )

supabase_admin: Client = create_client(supabase_url, supabase_secret_key)
