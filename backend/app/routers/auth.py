from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.db.supabase_client import supabase

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
        return {"message": "Account created successfully! Please check your email for verification.", "user": res.user}
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

        return {
            "message": "Login successful",
            "access_token": res.session.access_token,
            "user": res.user
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid email or password.")

@router.get("/profile")
def get_customer_profile(email: str):
    try:
        res = supabase.table("customers").select("*").eq("email", email).single()
        # support both attribute and dict-style responses
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail="Customer profile not found.")