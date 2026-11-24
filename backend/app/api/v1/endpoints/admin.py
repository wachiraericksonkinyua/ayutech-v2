# backend/app/api/v1/endpoints/admin.py

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr, Field, ValidationError
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import re
from supabase import create_client
from app.db.supabase_client import supabase_admin, supabase_url, supabase_key
from app.core.cache import product_cache
from app.core.auth_deps import require_admin, require_super_admin
from app.core.rate_limiter import limiter
from app.core.security import create_admin_token, verify_password
from app.api.v1.endpoints.orders import place_order_and_charge, _is_mpesa

router = APIRouter()
log = logging.getLogger("admin")

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
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    price: float = Field(gt=0)
    stock_quantity: int = Field(ge=0)
    part_number: Optional[str] = Field(default="", max_length=80)
    buying_price: Optional[float] = Field(default=0.0, ge=0)
    image_url: Optional[str] = ""
    supplier_name: Optional[str] = "Direct Importer"
    supplier_phone: Optional[str] = "254112323814"

# ==================== ORDERS ENDPOINTS ====================
@router.get("/orders", dependencies=_admin_guard)
async def get_admin_orders():
    try:
        res = supabase_admin.table("orders").select("*").order("created_at", desc=True).limit(100).execute()
        return {"status": "success", "orders": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _phone_core(raw) -> str:
    return re.sub(r"\D", "", str(raw or ""))[-9:]


@router.post("/auth/pin-login")
@limiter.limit("10/minute")
async def pin_login(request: Request, payload: dict):
    """Phone + PIN. PIN is bcrypt-hashed, checked against ONE account, with lockout."""
    identifier = str(payload.get("identifier", "")).strip()
    pin = str(payload.get("pin", "")).strip()
    core = _phone_core(identifier)
    bad = HTTPException(status_code=401, detail="Invalid phone or PIN")

    if len(core) != 9 or not pin.isdigit() or not (4 <= len(pin) <= 8):
        raise bad

    res = supabase_admin.table("staff_users").select(
        "id,name,role,phone,email,active,pin_hash,pin_failed_attempts,pin_locked_until"
    ).execute()
    staff = next((u for u in (res.data or []) if _phone_core(u.get("phone")) == core), None)

    if not staff or not staff.get("pin_hash"):
        raise bad
    if staff.get("active") is False:
        raise HTTPException(status_code=403, detail="This staff account is disabled.")

    now = datetime.now(timezone.utc)
    locked = staff.get("pin_locked_until")
    if locked and datetime.fromisoformat(str(locked).replace("Z", "+00:00")) > now:
        raise HTTPException(status_code=429, detail="Too many wrong PINs. Try again in 15 minutes.")

    if not verify_password(pin, staff["pin_hash"]):
        fails = (staff.get("pin_failed_attempts") or 0) + 1
        upd = {"pin_failed_attempts": fails}
        if fails >= 5:
            upd = {"pin_failed_attempts": 0,
                   "pin_locked_until": (now + timedelta(minutes=15)).isoformat()}
        supabase_admin.table("staff_users").update(upd).eq("id", staff["id"]).execute()
        raise bad

    supabase_admin.table("staff_users").update(
        {"pin_failed_attempts": 0, "pin_locked_until": None}).eq("id", staff["id"]).execute()

    token = create_admin_token({
        "sub": str(staff["id"]),
        "name": staff.get("name", "Staff"),
        "role": staff.get("role", "staff"),
    })
    safe = {k: v for k, v in staff.items()
            if k not in ("pin_hash", "pin_failed_attempts", "pin_locked_until")}
    return {"status": "success", "access_token": token, "user": safe}


class PosSaleItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    qty: int = Field(ge=1, le=1000)


class PosSaleRequest(BaseModel):
    items: List[PosSaleItem] = Field(min_items=1, max_items=30)
    payment_method: str = Field(min_length=1, max_length=40)
    customer_phone: str = Field(default="", max_length=32)
    payment_reference: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=500)


class RefillRequest(BaseModel):
    product_id: Optional[str] = Field(default=None, max_length=64)
    product_name: str = Field(default="Spare Part", min_length=1, max_length=160)
    requested_qty: int = Field(default=5, ge=1, le=100000)
    supplier_name: str = Field(default="Direct Importer", max_length=120)
    supplier_phone: str = Field(default="", max_length=32)
    notes: str = Field(default="", max_length=500)


async def _pos_sale_core(staff: dict, items: list, method: str, phone: str,
                         reference: str, notes: str) -> dict:
    method = (method or "").strip() or "Cash"
    is_mpesa = _is_mpesa(method)
    if not items:
        raise HTTPException(400, "Cart is empty.")
    if is_mpesa and not phone.strip():
        raise HTTPException(400, "Customer phone is required for M-Pesa.")
    if not is_mpesa and "cash" not in method.lower() and not reference.strip():
        raise HTTPException(400, "A payment reference is required for this payment method.")

    result = await place_order_and_charge(
        customer_id=None, phone=phone, fulfillment="pickup", location="Shop Counter",
        delivery_address="", payment_method=method,
        items=[{"id": i["id"], "qty": i["qty"]} for i in items],
        channel="pos", sold_by=str(staff["id"]))
    order = result["order"]

    if is_mpesa:
        return {"status": "pending_payment", "order_id": order["id"],
                "order_reference": order["order_reference"],
                "total": float(order["total_amount"])}

    try:
        paid = supabase_admin.rpc("mark_order_paid_manual", {
            "p_order_id": order["id"], "p_method": method,
            "p_reference": reference.strip().upper(),
            "p_staff_id": str(staff["id"]), "p_staff_name": staff.get("name", "Staff"),
            "p_notes": notes}).execute()
        paid_order = paid.data[0] if isinstance(paid.data, list) and paid.data else paid.data
        if not paid_order or paid_order.get("payment_status") != "paid":
            raise RuntimeError("Manual payment RPC returned no paid order.")
    except Exception:
        log.exception("Could not record manual payment for order %s", order["id"])
        try:
            supabase_admin.rpc("release_order_stock",
                               {"p_order_id": order["id"], "p_new_status": "Cancelled"}).execute()
        except Exception:
            log.exception("Could not release stock for failed POS sale %s", order["id"])
        raise HTTPException(500, "Could not record the payment. The sale needs staff review.")
    return {"status": "paid", "order_id": order["id"],
            "order_reference": order["order_reference"],
            "total": float(order["total_amount"])}


@router.post("/pos/sale")
async def pos_sale(body: PosSaleRequest, staff: dict = Depends(require_admin)):
    return await _pos_sale_core(
        staff, [i.dict() for i in body.items], body.payment_method,
        body.customer_phone, body.payment_reference, body.notes)


@router.post("/orders", deprecated=True)
async def create_admin_order(payload: dict, staff: dict = Depends(require_admin)):
    """Compatibility route; order totals and stock are still server-controlled."""
    try:
        body = PosSaleRequest.parse_obj(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    return await _pos_sale_core(
        staff, [item.dict() for item in body.items], body.payment_method,
        body.customer_phone, body.payment_reference, body.notes)


@router.get("/pos/sale/{order_id}")
async def pos_sale_status(order_id: str, staff: dict = Depends(require_admin)):
    r = supabase_admin.table("orders").select(
        "order_reference,status,payment_status,total_amount,receipt_number"
    ).eq("id", order_id).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "Order not found.")
    return r.data[0]


@router.post("/orders/manual-override")
async def process_manual_payment_override(payload: dict, staff: dict = Depends(require_admin)):
    items = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        try:
            items.append({"id": str(item["id"]), "qty": int(item.get("qty", 1))})
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid cart.")
    customer_phone = str(payload.get("customer_phone", ""))
    return await _pos_sale_core(
        staff, items, str(payload.get("payment_method", "Cash")),
        customer_phone if customer_phone.strip().isdigit() else "",
        str(payload.get("payment_reference", "")), str(payload.get("notes", "")))


@router.post("/orders/{order_id}/record-payment")
async def record_manual_payment(order_id: str, payload: dict, staff: dict = Depends(require_admin)):
    method = str(payload.get("payment_method", "Cash"))
    reference = str(payload.get("payment_reference", "")).strip().upper()
    if "cash" not in method.lower() and not reference:
        raise HTTPException(400, "A payment reference is required for this payment method.")
    try:
        paid = supabase_admin.rpc("mark_order_paid_manual", {
            "p_order_id": order_id, "p_method": method, "p_reference": reference,
            "p_staff_id": str(staff["id"]), "p_staff_name": staff.get("name", "Staff"),
            "p_notes": str(payload.get("notes", ""))}).execute()
        paid_order = paid.data[0] if isinstance(paid.data, list) and paid.data else paid.data
        if not paid_order or paid_order.get("payment_status") != "paid":
            raise RuntimeError("Manual payment RPC returned no paid order.")
    except Exception as e:
        if "order_not_payable" in str(e):
            raise HTTPException(409, "This order is not awaiting payment.")
        raise HTTPException(500, "Could not record the payment.")
    return {"status": "success"}


@router.patch("/orders/{order_id}/status")
async def update_order_status(order_id: str, payload: dict, staff: dict = Depends(require_admin)):
    """Status changes do not adjust stock or set payment state."""
    new_status = str(payload.get("status", "")).strip()
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing status")
    if new_status.lower() in ("paid", "payment failed"):
        raise HTTPException(status_code=400,
            detail="Payment is set by M-Pesa confirmation or a recorded manual payment.")
    if new_status not in ("Processing", "Fulfilled", "Cancelled"):
        raise HTTPException(400, "Unsupported order status.")

    r = supabase_admin.table("orders").select("id,payment_status,stock_released") \
        .eq("id", order_id).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Order not found")
    order = r.data[0]

    if new_status == "Fulfilled" and order["payment_status"] != "paid":
        raise HTTPException(409, "An order cannot be fulfilled before payment is recorded.")

    if new_status == "Cancelled" and order["payment_status"] == "pending" and not order["stock_released"]:
        supabase_admin.rpc("release_order_stock",
                           {"p_order_id": order_id, "p_new_status": "Cancelled"}).execute()
    else:
        supabase_admin.table("orders").update({"status": new_status}).eq("id", order_id).execute()
    return {"status": "success", "new_status": new_status}

# ==================== PRODUCTS ENDPOINTS ====================
@router.get("/products", dependencies=_admin_guard)
async def get_admin_products():
    try:
        res = supabase_admin.table("products").select("*").order("name", desc=False).execute()
        return getattr(res, "data", []) or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/products", dependencies=_admin_guard)
async def create_product(item: ProductEditPayload):
    try:
        res = supabase_admin.table("products").insert(item.dict()).execute()
        product_cache.invalidate()
        return {"status": "success", "product": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/products/{product_id}", dependencies=_admin_guard)
async def quick_stock_update(product_id: str, payload: dict):
    try:
        res = supabase_admin.table("products").update(payload).eq("id", product_id).execute()
        product_cache.invalidate()
        return {"status": "success", "data": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/products/{product_id}", dependencies=_admin_guard)
async def edit_full_product(product_id: str, payload: ProductEditPayload):
    try:
        res = supabase_admin.table("products").update(payload.dict()).eq("id", product_id).execute()
        product_cache.invalidate()
        return {"status": "success", "data": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/products/{product_id}", dependencies=_admin_guard)
async def delete_product(product_id: str):
    try:
        supabase_admin.table("products").delete().eq("id", product_id).execute()
        product_cache.invalidate()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== LEADS & BOT TAKEOVER ====================
@router.get("/leads", dependencies=_admin_guard)
async def get_admin_leads():
    try:
        res = supabase_admin.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
        return {"status": "success", "leads": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/leads/{lead_id}/takeover", dependencies=_admin_guard)
async def toggle_human_takeover(lead_id: str, payload: dict):
    new_status = str(payload.get("status", "human_takeover")).strip()
    try:
        clean_id = int(lead_id) if lead_id.isdigit() else lead_id
        res = supabase_admin.table("leads").update({"status": new_status}).eq("id", clean_id).execute()
        return {"status": "success", "new_status": new_status, "data": getattr(res, "data", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AUTH & REFILLS ====================
@router.get("/auth/staff-list", dependencies=_admin_guard)
async def get_staff_list():
    try:
        res = supabase_admin.table("staff_users").select("id, name, role, phone").execute()
        return {"users": getattr(res, "data", []) or []}
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
        auth_client = create_client(supabase_url, supabase_key)
        res = auth_client.auth.sign_in_with_password({
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


@router.post("/refills")
async def create_refill_request(payload: RefillRequest, staff: dict = Depends(require_admin)):
    try:
        clean_payload = {
            "product_id": payload.product_id or None,
            "product_name": payload.product_name,
            "requested_qty": payload.requested_qty,
            "requested_by_name": staff.get("name", "Staff"),
            "supplier_name": payload.supplier_name,
            "supplier_phone": payload.supplier_phone,
            "notes": payload.notes,
            "status": "pending_approval",
        }
        res = supabase_admin.table("refill_requests").insert(clean_payload).execute()
        return {"status": "success", "data": getattr(res, "data", []) or []}
    except Exception as e:
        print(f"Refill insert error: {e}")
        raise HTTPException(status_code=500, detail="Could not create the refill request.")

@router.get("/refills", dependencies=_admin_guard)
async def get_refill_requests():
    try:
        res = supabase_admin.table("refill_requests").select("*").order("created_at", desc=True).execute()
        return {"refills": getattr(res, "data", []) or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/refills/{refill_id}/status", dependencies=_admin_guard)
async def update_refill_status(refill_id: str, payload: dict):
    new_status = str(payload.get("status", "")).strip()
    if new_status.lower() not in ("pending_approval", "approved", "fulfilled", "rejected", "cancelled"):
        raise HTTPException(status_code=400, detail="Unsupported refill status.")
    try:
        result = supabase_admin.rpc("fulfill_refill_request", {
            "p_refill_id": refill_id,
            "p_new_status": new_status.lower(),
        }).execute()
        return {"status": "success", "new_status": new_status.lower(), "data": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics", dependencies=_admin_guard)
async def get_analytics():
    try:
        orders_res = supabase_admin.table("orders").select("*").execute()
        products_res = supabase_admin.table("products").select("*").execute()
        all_orders = getattr(orders_res, "data", []) or []
        all_products = getattr(products_res, "data", []) or []

        paid_orders = [o for o in all_orders if o.get("payment_status") == "paid"]
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