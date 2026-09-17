from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, EmailStr
from app.db.supabase_client import supabase
import uuid

router = APIRouter(prefix="/auth", tags=["Auth"])

class AuthPayload(BaseModel):
    email: EmailStr
    password: str

class ProfileUpdate(BaseModel):
    username: str = ""
    full_name: str = ""
    birth_date: str = ""
    gender: str = ""
    phone: str = ""
    avatar_url: str = ""
    banner_url: str = ""
    addresses: list = []

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


@router.get("/profile/{user_id}")
def get_customer_profile_by_id(user_id: str):
    try:
        res = supabase.table("customers").select("*").eq("id", user_id).single()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Customer profile not found.")


@router.patch("/profile/{user_id}")
def update_customer_profile(user_id: str, payload: ProfileUpdate):
    try:
        update_data = {k: v for k, v in payload.model_dump().items() if v not in [None, ""]}
        if not update_data:
            raise HTTPException(status_code=400, detail="Nothing to update.")

        # Upsert so a mirrored customer row is created if it doesn't exist yet
        res = supabase.table("customers").upsert({
            "id": user_id,
            **update_data,
        }, on_conflict="id").execute()

        updated = getattr(res, "data", None) or []
        return {"status": "success", "profile": updated[0] if updated else update_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update profile: {str(e)}")


@router.post("/upload-image/", status_code=201)
async def upload_profile_image(
    type: str = Query("avatar", pattern="^(avatar|banner)$"),
    image: UploadFile = File(...),
):
    try:
        contents = await image.read()
        file_extension = (image.filename or "image.jpg").split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        folder = "avatars" if type == "avatar" else "banners"
        file_path = f"{folder}/{unique_filename}"

        def _try_upload(bucket: str):
            supabase.storage.from_(bucket).upload(
                path=file_path,
                file=contents,
                file_options={"content-type": image.content_type or "image/jpeg"}
            )
            return supabase.storage.from_(bucket).get_public_url(file_path)

        try:
            image_url = _try_upload("profile-images")
        except Exception:
            # Bucket may not exist yet - try to create it automatically (service role)
            try:
                supabase.storage.create_bucket("profile-images", options={"public": True})
                image_url = _try_upload("profile-images")
            except Exception:
                # Last resort: reuse the existing product-images bucket so uploads still work
                image_url = _try_upload("product-images")
        return {"image_url": image_url, "type": type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")