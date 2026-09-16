from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from app.core.security import verify_password, get_password_hash, create_access_token
from app.db.supabase_client import supabase
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.db.supabase_client import supabase
from app.ui.state import current_user_id, user_info

router = APIRouter(prefix="/auth", tags=["Auth"])

class AuthPayload(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register_user(payload: AuthPayload):
    try:
        res = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password
        })
        
        user_obj = getattr(res, "user", None)
        if user_obj:
            user_id = user_obj.id if hasattr(user_obj, "id") else user_obj.get("id")
            # Automatically mirror user in public.customers table for relational mapping
            try:
                supabase.table("customers").upsert({
                    "id": user_id,
                    "email": payload.email
                }).execute()
            except Exception as db_err:
                print(f"Customer mirror warning: {db_err}")

        return {"message": "Account created successfully! Please check your email for verification.", "user": user_obj}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login_user(payload: AuthPayload):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        if res.session is None:
            raise HTTPException(status_code=401, detail="Login failed: no active session returned.")

        # res may be an object or dict depending on client; normalize
        session = getattr(res, "session", None) or (res.get("session") if isinstance(res, dict) else None)
        user_obj = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)

        if session is None:
            raise HTTPException(status_code=401, detail="Login failed: no active session returned.")

        user_id = None
        user_email = None
        if user_obj:
            user_id = user_obj.id if hasattr(user_obj, "id") else user_obj.get("id")
            user_email = user_obj.email if hasattr(user_obj, "email") else user_obj.get("email")

        return {
            "status": "success",
            "message": "Login successful",
            "user": {
                "id": str(user_id) if user_id is not None else None,
                "user_id": str(user_id) if user_id is not None else None,
                "email": user_email
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid email or password.")

@router.get("/profile")
def get_customer_profile(email: str):
    try:
        res = supabase.table("customers").select("*").eq("email", email).single()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Customer profile not found.")