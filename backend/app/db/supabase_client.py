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

# Server-only privileged client (service-role / secret key).
# Used to create staff auth users and bypass RLS for admin operations.
# NEVER expose this key to any client application.
supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
if supabase_secret_key:
    supabase_admin: Client = create_client(supabase_url, supabase_secret_key)
else:
    # Fall back to the publishable client so the app still imports; admin
    # operations that need elevated rights will return a clear error.
    supabase_admin = supabase
