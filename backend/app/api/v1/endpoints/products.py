from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from pydantic import BaseModel
import uuid
from app.db.supabase_client import supabase
from app.core.auth_deps import get_current_user
from app.core.cache import product_cache

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

# --- PYDANTIC SCHEMAS ---
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    part_number: Optional[str] = None
    category: str
    price: float
    stock_quantity: int
    image_url: Optional[str] = None

class ProductResponse(ProductCreate):
    id: int


# -------------------------------------------------------------
# GET: Retrieve all products or filter by category
# -------------------------------------------------------------
@router.get("/", response_model=List[dict])
async def get_products(category: Optional[str] = None):
    cache_key = f"products:{category or 'All'}"
    cached = product_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        query = supabase.table("products").select("*")

        if category and category != "All":
            query = query.eq("category", category)

        response = query.execute()
        data = response.data or []
        product_cache.set(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# -------------------------------------------------------------
# POST: Create Product via JSON Body
# -------------------------------------------------------------
@router.post("/", status_code=201)
async def create_product(product: ProductCreate, current_user: dict = Depends(get_current_user)):
    product_data = product.model_dump()

    try:
        db_response = supabase.table("products").insert(product_data).execute()
        product_cache.invalidate()
        return {"message": "Product created successfully", "data": db_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create product: {str(e)}")
# -------------------------------------------------------------
# POST: Upload Image File directly to Supabase Storage
# -------------------------------------------------------------
@router.post("/upload-image/", status_code=201)
async def upload_product_image(
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF images are allowed.")

        contents = await image.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image is too large. Maximum size is 5 MB.")

        # Safe filename extraction
        original_filename = image.filename or "image.jpg"
        file_extension = original_filename.split(".")[-1].lower()
        if file_extension not in {"jpg", "jpeg", "png", "webp", "gif"}:
            raise HTTPException(status_code=400, detail="Unsupported image file extension.")

        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"items/{unique_filename}"

        supabase.storage.from_("product-images").upload(
            path=file_path,
            file=contents,
            file_options={"content-type": content_type or "image/jpeg"}
        )

        image_url = supabase.storage.from_("product-images").get_public_url(file_path)
        return {"image_url": image_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")