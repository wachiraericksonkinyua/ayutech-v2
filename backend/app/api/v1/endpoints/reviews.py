from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from app.db.supabase_client import supabase

router = APIRouter()

class ReviewCreate(BaseModel):
    product_id: str
    customer_id: Optional[str] = None
    customer_name: str = "Customer"
    rating: int = Field(ge=1, le=5)
    comment: str = ""

@router.get("/product/{product_id}")
async def get_product_reviews(product_id: str):
    """Return rating summary + review list for a product."""
    try:
        res = supabase.table("reviews").select("*").eq("product_id", product_id).order("created_at", desc=True).execute()
        reviews = getattr(res, "data", None) or []
        count = len(reviews)
        average = round(sum(r.get("rating", 0) for r in reviews) / count, 1) if count else 0.0
        return {
            "product_id": product_id,
            "average": average,
            "count": count,
            "reviews": reviews,
        }
    except Exception as e:
        print(f"Fetch reviews error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load reviews: {str(e)}")

@router.post("/", status_code=201)
async def create_review(payload: ReviewCreate):
    """Submit a review. If a customer_id is supplied, the customer must have a
    Paid order containing this product (verified purchase)."""
    try:
        if payload.customer_id:
            cust_res = supabase.table("orders").select(
                "id", "status", "items"
            ).eq("customer_id", str(payload.customer_id)).execute()
            orders = getattr(cust_res, "data", None) or []
            verified = False
            for o in orders:
                if o.get("status") not in ["Paid", "Fulfilled"]:
                    continue
                items = o.get("items") or []
                if any(str(i.get("id")) == str(payload.product_id) for i in items):
                    verified = True
                    break
            if not verified:
                raise HTTPException(
                    status_code=403,
                    detail="Please checkout with this item first - only verified buyers can review products.",
                )

        row = {
            "product_id": str(payload.product_id),
            "customer_id": payload.customer_id,
            "customer_name": (payload.customer_name or "Customer").strip()[:60],
            "rating": int(payload.rating),
            "comment": (payload.comment or "").strip()[:1200],
        }
        res = supabase.table("reviews").insert(row).execute()
        created = (getattr(res, "data", None) or [{}])[0]
        return {"status": "success", "review": created}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Create review error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save review: {str(e)}")