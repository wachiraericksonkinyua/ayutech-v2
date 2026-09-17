# backend/app/api/v1/endpoints/admin.py

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import urllib.parse
import httpx
from app.db.supabase_client import supabase, supabase_admin
from app.core.cache import product_cache
from app.core.auth_deps import require_admin, require_super_admin
from app.core.rate_limiter import limiter
from app.core.security import create_admin_token

router = APIRouter()

# Every route in this router requires a staff token EXCEPT the login routes.
_admin_guard = [Depends(require_admin)]


class StaffLoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class StaffCreatePayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    role: str = "staff"
    phone: str = Field(default="", max_length=20)

def _ensure_list(v):
    return v if isinstance(v, list) else []

class ProductEditPayload(BaseModel):
    name: str
    category: str
    price: float
    stock_quantity: int
    part_number: Optional[str] = ""
    buying_price: Optional[float] = 0.0
    image_url: Optional[str] = ""
    supplier_name: Optional[str] = "Direct Importer"
    supplier_phone: Optional[str] = "254112323814"

# ==================== ORDERS ENDPOINTS ====================
@router.get("/orders", dependencies=_admin_guard)
async def get_admin_orders():
    try:
        res = supabase.table("orders").select("*").order("created_at", desc=True).limit(100).execute()
        return {"status": "success", "orders": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orders", dependencies=_admin_guard)
async def create_admin_order(payload: dict):
    try:
        res = supabase.table("orders").insert(payload).execute()
        return {"status": "success", "data": getattr(res, "data", []) or []}
    except Exception as e:
        print(f"Order creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orders/manual-override", dependencies=_admin_guard)
async def process_manual_payment_override(payload: dict):
    clean_ref = str(payload.get("payment_reference", "")).strip().upper()
    if not clean_ref:
        raise HTTPException(status_code=400, detail="Transaction receipt or reference code is required")

    items = payload.get("items", [])
    total_amount = float(payload.get("total_amount", 0))
    payment_method = str(payload.get("payment_method", "BANK_TRANSFER"))
    customer_phone = str(payload.get("customer_phone", "Walk-in Customer"))
    verified_by_name = str(payload.get("verified_by_name", "Staff"))
    notes = str(payload.get("notes", ""))
    order_ref = f"MAN-{datetime.now().strftime('%H%M%S')}"

    # 1. Deduct Stock
    for item in items:
        p_id = str(item.get("id", "")).strip()
        if not p_id or p_id == "None":
            continue
        try:
            qty_sold = int(item.get("qty", 1))
            p_res = supabase.table("products").select("stock_quantity").eq("id", p_id).execute()
            rows = getattr(p_res, "data", []) or []
            if rows:
                curr_stock = int(rows[0].get("stock_quantity") or 0)
                new_stock = max(0, curr_stock - qty_sold)
                supabase.table("products").update({"stock_quantity": new_stock}).eq("id", p_id).execute()
        except Exception as stock_err:
            print(f"Stock deduction warning for {p_id}: {stock_err}")

    # 2. Insert into orders table
    order_data = {
        "order_reference": order_ref,
        "customer_phone": customer_phone,
        "total_amount": total_amount,
        "status": "Fulfilled",
        "receipt_number": f"{clean_ref} ({verified_by_name})",
        "fulfillment": f"Shop Counter ({payment_method}) - Sold by {verified_by_name}",
        "items": items,
        "created_at": datetime.now().isoformat()
    }

    try:
        order_insert = supabase.table("orders").insert(order_data).execute()
        created_orders = getattr(order_insert, "data", []) or []
        created_order_id = created_orders[0].get("id") if created_orders else order_ref
    except Exception as e:
        print(f"Order insert error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record order: {str(e)}")

    return {
        "status": "success",
        "order_reference": order_ref,
        "payment_reference": clean_ref,
        "verified_by": verified_by_name,
        "total_amount": total_amount
    }

@router.patch("/orders/{order_id}/status", dependencies=_admin_guard)
async def update_order_status(order_id: str, payload: dict):
    new_status = str(payload.get("status", "")).strip()
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing status")

    try:
        res = supabase.table("orders").select("*").eq("id", order_id).execute()
        order_rows = getattr(res, "data", []) or []
        if not order_rows:
            raise HTTPException(status_code=404, detail="Order not found")
        order = order_rows[0]
        prev_status = str(order.get("status", ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database fetch error: {str(e)}")

    if new_status == "Fulfilled" and prev_status != "Fulfilled":
        items_list = _ensure_list(order.get("items", []))
        for item in items_list:
            if not isinstance(item, dict):
                continue
            p_id = str(item.get("id", "")).strip()
            if not p_id or p_id == "None":
                continue
            try:
                qty_sold = int(item.get("qty", 1))
            except (ValueError, TypeError):
                qty_sold = 1
            try:
                p_res = supabase.table("products").select("stock_quantity").eq("id", p_id).execute()
                p_rows = getattr(p_res, "data", []) or []
                if p_rows:
                    curr_stock = int(p_rows[0].get("stock_quantity") or 0)
                    new_stock = max(0, curr_stock - qty_sold)
                    supabase.table("products").update({"stock_quantity": new_stock}).eq("id", p_id).execute()
            except Exception as stock_err:
                print(f"Stock deduction error for item {p_id}: {stock_err}")

    try:
        supabase.table("orders").update({"status": new_status}).eq("id", order_id).execute()
    except Exception as upd_err:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(upd_err)}")

    return {"status": "success", "new_status": new_status}

# ==================== PRODUCTS ENDPOINTS ====================
@router.get("/products", dependencies=_admin_guard)
async def get_admin_products():
    try:
        res = supabase.table("products").select("*").order("name", desc=False).execute()
        return getattr(res, "data", []) or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/products", dependencies=_admin_guard)
async def create_product(item: ProductEditPayload):
    try:
        res = supabase.table("products").insert(item.dict()).execute()
        product_cache.invalidate()
        return {"status": "success", "product": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/products/{product_id}", dependencies=_admin_guard)
async def quick_stock_update(product_id: str, payload: dict):
    try:
        res = supabase.table("products").update(payload).eq("id", product_id).execute()
        product_cache.invalidate()
        return {"status": "success", "data": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/products/{product_id}", dependencies=_admin_guard)
async def edit_full_product(product_id: str, payload: ProductEditPayload):
    try:
        res = supabase.table("products").update(payload.dict()).eq("id", product_id).execute()
        product_cache.invalidate()
        return {"status": "success", "data": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/products/{product_id}", dependencies=_admin_guard)
async def delete_product(product_id: str):
    try:
        supabase.table("products").delete().eq("id", product_id).execute()
        product_cache.invalidate()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== LEADS & BOT TAKEOVER ====================
@router.get("/leads", dependencies=_admin_guard)
async def get_admin_leads():
    try:
        res = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
        return {"status": "success", "leads": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/leads/{lead_id}/takeover", dependencies=_admin_guard)
async def toggle_human_takeover(lead_id: str, payload: dict):
    new_status = str(payload.get("status", "human_takeover")).strip()
    try:
        clean_id = int(lead_id) if lead_id.isdigit() else lead_id
        res = supabase.table("leads").update({"status": new_status}).eq("id", clean_id).execute()
        return {"status": "success", "new_status": new_status, "data": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AUTH & REFILLS ====================
@router.get("/auth/staff-list", dependencies=_admin_guard)
async def get_staff_list():
    try:
        res = supabase.table("staff_users").select("id, name, role, phone").execute()
        return {"users": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/pin-login")
@limiter.limit("10/minute")
async def pin_login(request: Request, payload: dict):
    identifier = str(payload.get("identifier", "")).strip().lower()
    pin = str(payload.get("pin", "")).strip()

    if not pin:
        raise HTTPException(status_code=400, detail="PIN is required")

    clean_digits = "".join(c for c in identifier if c.isdigit())
    if clean_digits.startswith("254") and len(clean_digits) == 12:
        core_digits = clean_digits[3:]
    elif clean_digits.startswith("0") and len(clean_digits) == 10:
        core_digits = clean_digits[1:]
    else:
        core_digits = clean_digits

    try:
        res = supabase_admin.table("staff_users").select("*").execute()
        users = getattr(res, "data", []) or []
        for u in users:
            u_pin = str(u.get("pin_code", "")).strip()
            u_phone = str(u.get("phone", "")).strip().replace("+", "").replace(" ", "")
            u_name = str(u.get("name", "")).strip().lower()
            if u_pin == pin:
                if not identifier or (core_digits and core_digits in u_phone) or (identifier in u_name):
                    # Never return the PIN back to the client
                    safe_user = {k: v for k, v in u.items() if k != "pin_code"}
                    token = create_admin_token({
                        "sub": str(u.get("id", "")),
                        "name": u.get("name", "Staff"),
                        "role": u.get("role", "staff"),
                    })
                    return {"status": "success", "access_token": token, "user": safe_user}
        raise HTTPException(status_code=401, detail="Invalid Phone/Name or PIN")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _find_staff_for_user(user_id: str, email: str):
    """Look up the staff_users row linked to an auth user (by id, then email)."""
    try:
        res = supabase_admin.table("staff_users").select("*").eq(
            "auth_user_id", str(user_id)
        ).limit(1).execute()
        rows = getattr(res, "data", None) or []
        if rows:
            return rows[0]
    except Exception:
        pass
    try:
        res2 = supabase_admin.table("staff_users").select("*").ilike(
            "email", email
        ).limit(1).execute()
        rows2 = getattr(res2, "data", None) or []
        if rows2:
            return rows2[0]
    except Exception:
        pass
    return None


@router.post("/auth/login")
@limiter.limit("10/minute")
async def staff_login(request: Request, payload: StaffLoginPayload):
    """Email + password login for staff (Supabase Auth), issues a staff token."""
    try:
        res = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password,
        })
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_obj = getattr(res, "user", None) or (res.get("user") if isinstance(res, dict) else None)
    if user_obj is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_id = user_obj.id if hasattr(user_obj, "id") else user_obj.get("id")
    staff = _find_staff_for_user(str(user_id), payload.email)
    if not staff:
        raise HTTPException(status_code=403, detail="This account is not a staff account.")
    if not staff.get("active", True):
        raise HTTPException(status_code=403, detail="This staff account is disabled.")

    safe_staff = {k: v for k, v in staff.items() if k != "pin_code"}
    token = create_admin_token({
        "sub": str(staff.get("id", "")),
        "name": staff.get("name", "Staff"),
        "role": staff.get("role", "staff"),
    })
    return {"status": "success", "access_token": token, "user": safe_staff}


@router.get("/staff", dependencies=[Depends(require_super_admin)])
async def list_staff():
    try:
        res = supabase_admin.table("staff_users").select(
            "id, auth_user_id, email, name, role, phone, active"
        ).order("name").execute()
        return {"staff": getattr(res, "data", None) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/staff", status_code=201, dependencies=[Depends(require_super_admin)])
async def create_staff(payload: StaffCreatePayload):
    """Create a Supabase Auth user and link a staff_users record."""
    # 1) Create the auth login
    try:
        created = supabase_admin.auth.admin.create_user({
            "email": payload.email,
            "password": payload.password,
            "email_confirm": True,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not create login: {e}")

    new_user = getattr(created, "user", None) or (created.get("user") if isinstance(created, dict) else None)
    auth_user_id = None
    if new_user is not None:
        auth_user_id = new_user.id if hasattr(new_user, "id") else new_user.get("id")

    # 2) Link the staff record
    try:
        ins = supabase_admin.table("staff_users").insert({
            "auth_user_id": str(auth_user_id) if auth_user_id else None,
            "email": payload.email,
            "name": payload.name,
            "role": payload.role or "staff",
            "phone": payload.phone,
            "active": True,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login created but staff record failed: {e}")

    rows = getattr(ins, "data", None) or []
    return {"status": "success", "staff": rows[0] if rows else None}


@router.patch("/staff/{staff_id}", dependencies=[Depends(require_super_admin)])
async def update_staff(staff_id: str, payload: dict):
    allowed = {
        k: payload[k] for k in ("name", "role", "phone", "active")
        if k in payload
    }
    if not allowed:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    try:
        res = supabase_admin.table("staff_users").update(allowed).eq("id", staff_id).execute()
        rows = getattr(res, "data", None) or []
        return {"status": "success", "staff": rows[0] if rows else allowed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/staff/{staff_id}", dependencies=[Depends(require_super_admin)])
async def delete_staff(staff_id: str):
    try:
        sr = supabase_admin.table("staff_users").select("auth_user_id").eq("id", staff_id).limit(1).execute()
        rows = getattr(sr, "data", None) or []
        auth_id = rows[0].get("auth_user_id") if rows else None
    except Exception:
        auth_id = None

    try:
        supabase_admin.table("staff_users").delete().eq("id", staff_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if auth_id:
        try:
            supabase_admin.auth.admin.delete_user(auth_id)
        except Exception as e:
            print(f"Auth user delete warning: {e}")

    return {"status": "success"}


    try:
        clean_payload = {
            "product_id": str(payload.get("product_id", "")),
            "product_name": str(payload.get("product_name", "Spare Part")),
            "requested_qty": int(payload.get("requested_qty", 5)),
            "requested_by_name": str(payload.get("requested_by_name", "Staff")),
            "supplier_name": str(payload.get("supplier_name", "Direct Importer")),
            "supplier_phone": str(payload.get("supplier_phone", "254112323814")),
            "notes": str(payload.get("notes", "")),
            "status": "pending_approval"
        }
        res = supabase.table("refill_requests").insert(clean_payload).execute()
        return {"status": "success", "data": getattr(res, "data", []) or []}
    except Exception as e:
        print(f"Refill insert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/refills", dependencies=_admin_guard)
async def get_refill_requests():
    try:
        res = supabase.table("refill_requests").select("*").order("created_at", desc=True).execute()
        return {"refills": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/refills/{refill_id}/status", dependencies=_admin_guard)
async def update_refill_status(refill_id: str, payload: dict):
    new_status = str(payload.get("status", "")).strip()
    try:
        ref_res = supabase.table("refill_requests").select("*").eq("id", refill_id).execute()
        refill_rows = getattr(ref_res, "data", []) or []
        if not refill_rows:
            raise HTTPException(status_code=404, detail="Refill request not found")
        
        refill_item = refill_rows[0]
        prev_status = str(refill_item.get("status", ""))
        product_id = str(refill_item.get("product_id", "")).strip()
        add_qty = int(refill_item.get("requested_qty", 0) or 0)

        # Increment product stock on fulfillment
        if new_status == "fulfilled" and prev_status != "fulfilled" and product_id and product_id != "None":
            p_res = supabase.table("products").select("stock_quantity").eq("id", product_id).execute()
            p_rows = getattr(p_res, "data", []) or []
            if p_rows:
                curr_stock = int(p_rows[0].get("stock_quantity") or 0)
                new_stock = curr_stock + add_qty
                supabase.table("products").update({"stock_quantity": new_stock}).eq("id", product_id).execute()

        res = supabase.table("refill_requests").update({"status": new_status}).eq("id", refill_id).execute()
        return {"status": "success", "new_status": new_status, "data": getattr(res, "data", [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics", dependencies=_admin_guard)
async def get_analytics():
    try:
        orders_res = supabase.table("orders").select("*").execute()
        products_res = supabase.table("products").select("*").execute()
        all_orders = getattr(orders_res, "data", []) or []
        all_products = getattr(products_res, "data", []) or []

        paid_orders = [o for o in all_orders if o.get("status") in ["Paid", "Fulfilled"]]
        total_rev = sum(float(o.get("total_amount") or o.get("total") or 0) for o in paid_orders)
        depleted = [p for p in all_products if int(p.get("stock_quantity", 0) or 0) <= 2]

        item_sales = {}
        for ord_data in paid_orders:
            for itm in _ensure_list(ord_data.get("items", []) or []):
                if not isinstance(itm, dict):
                    continue
                name = itm.get("name", "Spare Part")
                try:
                    qty = int(itm.get("qty", 1))
                except (TypeError, ValueError):
                    qty = 1
                item_sales[name] = item_sales.get(name, 0) + qty

        top_sellers = sorted([{"name": k, "units_sold": v} for k, v in item_sales.items()], key=lambda x: x["units_sold"], reverse=True)[:5]

        return {
            "total_revenue": total_rev,
            "paid_orders_count": len(paid_orders),
            "depleted_products": depleted,
            "top_selling_products": top_sellers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))