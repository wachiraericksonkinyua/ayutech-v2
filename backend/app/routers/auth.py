from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Request, Depends
from pydantic import BaseModel, EmailStr, Field
from app.db.supabase_client import supabase
from app.core.rate_limiter import limiter
from app.core.auth_deps import get_current_user, require_owner
import uuid

router = APIRouter(prefix="/auth", tags=["Auth"])

# Upload guards
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


class AuthPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class ProfileUpdate(BaseModel):
    username: str = Field(default="", max_length=50)
    full_name: str = Field(default="", max_length=120)
    birth_date: str = Field(default="", max_length=20)
    gender: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=20)
    avatar_url: str = Field(default="", max_length=500)
    banner_url: str = Field(default="", max_length=500)
    addresses: list = Field(default_factory=list)


@router.post("/register")
@limiter.limit("5/minute")
def register_user(request: Request, payload: AuthPayload):
    try:
        res = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password
        })
        return {"message": "Account created successfully! Please check your email for verification.", "user": res.user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
@limiter.limit("10/minute")
def login_user(request: Request, payload: AuthPayload):
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
def get_customer_profile(email: str, current_user: dict = Depends(get_current_user)):
    """Fetch the caller's own profile by email."""
    if str(current_user.get("email", "")).lower() != email.strip().lower():
        raise HTTPException(status_code=403, detail="You can only access your own account.")
    try:
        res = supabase.table("customers").select("*").eq("email", email).single()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Customer profile not found.")


@router.get("/profile/{user_id}")
def get_customer_profile_by_id(user_id: str, current_user: dict = Depends(require_owner)):
    try:
        res = supabase.table("customers").select("*").eq("id", user_id).single()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        if not data:
            raise HTTPException(status_code=404, detail="Customer profile not found.")
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Customer profile not found.")


@router.patch("/profile/{user_id}")
def update_customer_profile(
    user_id: str,
    payload: ProfileUpdate,
    current_user: dict = Depends(require_owner),
):
    try:
        update_data = {
            k: v for k, v in payload.model_dump().items()
            if v not in [None, ""] or k == "addresses"
        }
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
    request: Request,
    type: str = Query("avatar", pattern="^(avatar|banner)$"),
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        # Validate declared content type
        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF images are allowed.")

        # Validate extension
        file_extension = (image.filename or "image.jpg").split(".")[-1].lower()
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported image file extension.")

        contents = await image.read()

        # Validate size
        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image is too large. Maximum size is 5 MB.")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Validate magic bytes so a renamed script can't be stored as an image
        if not _looks_like_image(contents):
            raise HTTPException(status_code=400, detail="File does not appear to be a valid image.")

        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        folder = "avatars" if type == "avatar" else "banners"
        file_path = f"{folder}/{unique_filename}"

        def _try_upload(bucket: str):
            supabase.storage.from_(bucket).upload(
                path=file_path,
                file=contents,
                file_options={"content-type": content_type or "image/jpeg"}
            )
            return supabase.storage.from_(bucket).get_public_url(file_path)

        try:
            image_url = _try_upload("profile-images")
        except Exception:
            # Bucket may not exist yet - try to create it automatically
            try:
                supabase.storage.create_bucket("profile-images", options={"public": True})
                image_url = _try_upload("profile-images")
            except Exception:
                # Last resort: reuse the existing product-images bucket so uploads still work
                image_url = _try_upload("product-images")
        return {"image_url": image_url, "type": type}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")


def _looks_like_image(data: bytes) -> bool:
    """Check common image magic numbers."""
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":            # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":       # PNG
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):     # GIF
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WEBP
        return True
    return False
