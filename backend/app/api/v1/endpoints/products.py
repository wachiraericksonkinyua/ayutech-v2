from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from pydantic import BaseModel
import uuid
from app.db.supabase_client import supabase

router = APIRouter()

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
    try:
        query = supabase.table("products").select("*")
        
        if category and category != "All":
            query = query.eq("category", category)
            
        response = query.execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# -------------------------------------------------------------
# POST: Create Product via JSON Body
# -------------------------------------------------------------
@router.post("/", status_code=201)
async def create_product(product: ProductCreate):
    product_data = product.model_dump()

    try:
        db_response = supabase.table("products").insert(product_data).execute()
        return {"message": "Product created successfully", "data": db_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create product: {str(e)}")
# -------------------------------------------------------------
# POST: Upload Image File directly to Supabase Storage
# -------------------------------------------------------------
@router.post("/upload-image/", status_code=201)
async def upload_product_image(image: UploadFile = File(...)):
    try:
        contents = await image.read()
        
        # Safe filename extraction
        original_filename = image.filename or "image.jpg"
        file_extension = original_filename.split(".")[-1]
        
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"items/{unique_filename}"

        supabase.storage.from_("product-images").upload(
            path=file_path,
            file=contents,
            file_options={"content-type": image.content_type or "image/jpeg"}
        )

        image_url = supabase.storage.from_("product-images").get_public_url(file_path)
        return {"image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")