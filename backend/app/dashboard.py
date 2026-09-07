# backend/app/dashboard.py

import flet as ft
import httpx
import urllib.parse
import threading
import time
from datetime import datetime, date
from app.ui.state import API_BASE_URL

def format_order_date(date_str: str) -> str:
    if not date_str:
        return "Recent"
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return str(date_str)[:16].replace("T", " ")

def normalize_phone_kenya(phone_raw: str) -> str:
    clean = "".join(c for c in str(phone_raw or "") if c.isdigit())
    if clean.startswith("0") and len(clean) == 10:
        return f"254{clean[1:]}"
    if clean.startswith("254") and len(clean) == 12:
        return clean
    if len(clean) == 9:
        return f"254{clean}"
    return clean

def open_whatsapp_chat(page: ft.Page, phone: str, message: str):
    clean_p = normalize_phone_kenya(phone)
    if not clean_p or len(clean_p) < 9:
        return
    encoded_text = urllib.parse.quote(message)
    page.launch_url(f"https://api.whatsapp.com/send?phone={clean_p}&text={encoded_text}")

def main(page: ft.Page):
    page.title = "AyuTech Motors - Management & Multi-Item POS"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#F9FAFB"

    window = getattr(page, "window", None)
    if window is not None:
        window.width = 1240
        window.height = 880
        window.min_width = 380
        window.min_height = 650
        window.resizable = True

    current_user = {"name": "Guest", "role": None, "phone": ""}
    orders_data = []
    products_data = []
    leads_data = []
    refills_data = []
    analytics_data = {}
    active_nav_index = 0
    pos_cart = []

    main_layout = ft.Container(expand=True)
    content_area = ft.Container(expand=True, padding=ft.padding.symmetric(horizontal=16, vertical=12))

    def show_toast(msg: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            ft.Text(msg, color="white", weight=ft.FontWeight.BOLD),
            bgcolor="#DC2626" if is_error else "#25D366"
        )
        page.snack_bar.open = True
        page.update()

    # ==================== DATA FETCHERS ====================
    def fetch_all_orders():
        nonlocal orders_data
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/orders", timeout=4)
            if res.status_code == 200:
                orders_data = res.json().get("orders", [])
        except Exception as e:
            print(f"Fetch orders error: {e}")

    def fetch_all_products():
        nonlocal products_data
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/products", timeout=4)
            if res.status_code == 200:
                products_data = res.json()
        except Exception as e:
            print(f"Fetch products error: {e}")

    def fetch_all_leads():
        nonlocal leads_data
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/leads", timeout=4)
            if res.status_code == 200:
                leads_data = res.json().get("leads", [])
        except Exception as e:
            print(f"Fetch leads error: {e}")

    def fetch_refills():
        nonlocal refills_data
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/refills", timeout=4)
            if res.status_code == 200:
                refills_data = res.json().get("refills", [])
        except Exception as e:
            print(f"Fetch refills error: {e}")

    def fetch_analytics():
        nonlocal analytics_data
        if current_user.get("role") != "admin":
            return
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/analytics", timeout=4)
            if res.status_code == 200:
                analytics_data = res.json()
        except Exception as e:
            print(f"Fetch analytics error: {e}")

    def refresh_all_data():
        fetch_all_orders()
        fetch_all_products()
        fetch_all_leads()
        fetch_refills()
        fetch_analytics()
        render_current_tab()
        show_toast("Data refreshed!")

    def get_existing_categories():
        cats = sorted(list({p.get("category", "General") for p in products_data if p.get("category")}))
        return cats if cats else ["Engine Parts", "Suspension Parts", "Brake Parts", "Body Parts", "Gear Parts", "Service Parts"]

    def send_customer_receipt_whatsapp(cust_phone: str, order_ref: str, payment_mode: str | None, total_val: float, order_items: list):
        payment_mode = payment_mode or "Cash"
        cashier_str = f"{current_user.get('name', 'Staff')} ({current_user.get('phone') or 'Counter'})"
        items_rows = "\n".join([
            f"• {it['name']} [{it.get('part_number') or 'N/A'}] (x{it['qty']}) = KES {float(it['price'])*int(it['qty']):,.0f}"
            for it in order_items
        ])
        receipt_text = f"""*AYUTECH MOTORS LIMITED*
*Official Payment Receipt*
----------------------------------------
*Receipt No:* #{order_ref}
*Date:* {datetime.now().strftime('%d %b %Y, %H:%M')}
*Cashier:* {cashier_str}
----------------------------------------
*ITEMS PURCHASED:*
{items_rows}
----------------------------------------
*TOTAL PAID: KES {total_val:,.0f}*
*Payment Mode:* {payment_mode}
*Status:* Confirmed

📍 *Location:* Kirinyaga Road, Nairobi
📞 *Helpline:* +254112323814
Thank you for choosing AyuTech Motors!"""
        open_whatsapp_chat(page, cust_phone, receipt_text)

    # ==================== MODALS ====================
    def open_add_product_dialog(e=None):
        p_name = ft.TextField(label="Spare Part Name", height=42, text_size=12)
        p_num = ft.TextField(label="Part Number", height=42, text_size=12)
        categories = get_existing_categories()
        cat_options = [ft.dropdown.Option(c) for c in categories] + [ft.dropdown.Option("+ Add New Category")]
        
        p_cat_dropdown = ft.Dropdown(
            label="Category",
            options=cat_options,
            value=categories[0] if categories else "General",
            height=42,
            text_size=12
        )
        p_custom_cat = ft.TextField(label="New Category", visible=False, height=42, text_size=12)

        def on_category_change(ev):
            p_custom_cat.visible = (p_cat_dropdown.value == "+ Add New Category")
            dlg.update()

        p_cat_dropdown.on_change = on_category_change
        p_buy_price = ft.TextField(label="Buying Cost Price (KES)", value="0", visible=(current_user.get("role") == "admin"), height=42, text_size=12)
        p_price = ft.TextField(label="Selling Retail Price (KES)", height=42, text_size=12)
        p_stock = ft.TextField(label="Initial Stock", value="10", height=42, text_size=12)
        p_sup = ft.TextField(label="Supplier Name", value="Direct Importer", height=42, text_size=12)
        p_phone = ft.TextField(label="Supplier Phone", value="254112323814", height=42, text_size=12)

        def submit_new_product(ev):
            chosen_cat = (p_custom_cat.value if p_cat_dropdown.value == "+ Add New Category" else p_cat_dropdown.value) or "General"
            try:
                payload = {
                    "name": (p_name.value or "").strip(),
                    "part_number": (p_num.value or "").strip(),
                    "category": chosen_cat.strip(),
                    "buying_price": float((p_buy_price.value or "0").strip()) if current_user.get("role") == "admin" else 0.0,
                    "price": float((p_price.value or "0").strip()),
                    "stock_quantity": int((p_stock.value or "0").strip()),
                    "supplier_name": (p_sup.value or "").strip() or "Direct Importer",
                    "supplier_phone": (p_phone.value or "").strip() or "254112323814"
                }
                res = httpx.post(f"{API_BASE_URL}/admin/products", json=payload, timeout=4)
                if res.status_code in [200, 201]:
                    dlg.open = False
                    show_toast(f"Added {p_name.value} to catalog!")
                    fetch_all_products()
                    render_current_tab()
                else:
                    show_toast(f"Failed to add: {res.text}", is_error=True)
            except Exception as err:
                show_toast(f"Error: {err}", is_error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Add Auto Part to Catalog", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column([p_name, p_num, p_cat_dropdown, p_custom_cat, p_buy_price, p_price, p_stock, p_sup, p_phone], tight=True, spacing=8)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: (setattr(dlg, "open", False), page.update())),
                ft.ElevatedButton("Save to Catalog", bgcolor="#DC2626", color="white", on_click=submit_new_product)
            ]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def open_edit_product_dialog(product: dict):
        if not product:
            return

        prod_id = product.get("id")
        p_name = ft.TextField(label="Spare Part Name", value=product.get("name", ""), height=42, text_size=12)
        p_num = ft.TextField(label="Part Number", value=product.get("part_number", ""), height=42, text_size=12)
        categories = get_existing_categories()
        cat_options = [ft.dropdown.Option(c) for c in categories] + [ft.dropdown.Option("+ Add New Category")]
        current_category = product.get("category") or "General"

        p_cat_dropdown = ft.Dropdown(
            label="Category",
            options=cat_options,
            value=current_category if current_category in categories else (categories[0] if categories else "General"),
            height=42,
            text_size=12
        )
        p_custom_cat = ft.TextField(label="New Category", visible=False, height=42, text_size=12)

        def on_category_change(ev):
            p_custom_cat.visible = (p_cat_dropdown.value == "+ Add New Category")
            dlg.update()

        p_cat_dropdown.on_change = on_category_change
        p_buy_price = ft.TextField(label="Cost Price (KES)", value=str(product.get("buying_price", 0)), visible=(current_user.get("role") == "admin"), height=42, text_size=12)
        p_price = ft.TextField(label="Retail Price (KES)", value=str(product.get("price", 0)), height=42, text_size=12)
        p_stock = ft.TextField(label="Stock Quantity", value=str(product.get("stock_quantity", 0)), read_only=(current_user.get("role") != "admin"), height=42, text_size=12)
        p_sup = ft.TextField(label="Supplier Name", value=product.get("supplier_name", "Direct Importer"), height=42, text_size=12)
        p_phone = ft.TextField(label="Supplier Phone", value=product.get("supplier_phone", "254112323814"), height=42, text_size=12)

        def submit_edit_product(ev):
            chosen_cat = (p_custom_cat.value if p_cat_dropdown.value == "+ Add New Category" else p_cat_dropdown.value) or "General"
            try:
                payload = {
                    "name": (p_name.value or "").strip(),
                    "part_number": (p_num.value or "").strip(),
                    "category": chosen_cat.strip(),
                    "buying_price": float((p_buy_price.value or "0").strip()) if current_user.get("role") == "admin" else float(product.get("buying_price", 0) or 0),
                    "price": float((p_price.value or "0").strip()),
                    "supplier_name": (p_sup.value or "").strip() or "Direct Importer",
                    "supplier_phone": (p_phone.value or "").strip() or "254112323814"
                }
                if current_user.get("role") == "admin":
                    payload["stock_quantity"] = int((p_stock.value or "0").strip())

                res = httpx.patch(f"{API_BASE_URL}/admin/products/{prod_id}", json=payload, timeout=4)
                if res.status_code in [200, 204]:
                    dlg.open = False
                    show_toast("Product updated successfully!")
                    fetch_all_products()
                    render_current_tab()
                else:
                    show_toast(f"Update error: {res.text}", is_error=True)
            except Exception as err:
                show_toast(f"Update error: {err}", is_error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Edit Part Information", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column([p_name, p_num, p_cat_dropdown, p_custom_cat, p_buy_price, p_price, p_stock, p_sup, p_phone], tight=True, spacing=8)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: (setattr(dlg, "open", False), page.update())),
                ft.ElevatedButton("Save Changes", bgcolor="#2563EB", color="white", on_click=submit_edit_product)
            ]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def open_refill_dialog(product: dict):
        pid = str(product.get("id"))
        pname = product.get("name")
        pn = product.get("part_number") or ""
        sname_input = ft.TextField(label="Supplier Name", value=product.get("supplier_name", "Direct Importer"), height=42, text_size=12)
        sphone_input = ft.TextField(label="Supplier Phone (254...)", value=product.get("supplier_phone", "254112323814"), height=42, text_size=12)
        qty_input = ft.TextField(label="Quantity to Request", value="5", height=42, text_size=12)
        notes_input = ft.TextField(label="Urgency / Notes (e.g. Customer waiting)", value="", height=42, text_size=12)

        def submit_refill(ev):
            try:
                r_qty = int((qty_input.value or "5").strip())
            except ValueError:
                r_qty = 5

            payload = {
                "product_id": pid,
                "product_name": f"{pname} ({pn})" if pn else pname,
                "requested_qty": r_qty,
                "requested_by_name": f"{current_user.get('name', 'Staff')} ({current_user.get('phone', 'Counter')})",
                "supplier_name": (sname_input.value or "").strip() or "Direct Importer",
                "supplier_phone": (sphone_input.value or "").strip() or "254112323814",
                "notes": (notes_input.value or "").strip(),
                "status": "pending_approval"
            }
            try:
                res = httpx.post(f"{API_BASE_URL}/admin/refills", json=payload, timeout=4)
                if res.status_code in [200, 201]:
                    dlg_refill.open = False
                    show_toast("Refill request submitted for approval!")
                    fetch_refills()
                    render_current_tab()
                else:
                    show_toast(f"Refill error: {res.text}", is_error=True)
            except Exception as err:
                show_toast(f"Connection error: {err}", is_error=True)

        dlg_refill = ft.AlertDialog(
            title=ft.Text(f"Request Refill: {pname}", weight=ft.FontWeight.BOLD, size=14),
            content=ft.Container(
                width=400,
                content=ft.Column([
                    ft.Text(f"Current Stock: {product.get('stock_quantity', 0)} units", size=12, color="#DC2626", weight=ft.FontWeight.BOLD),
                    qty_input,
                    sname_input,
                    sphone_input,
                    notes_input
                ], tight=True, spacing=8)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: (setattr(dlg_refill, "open", False), page.update())),
                ft.ElevatedButton("Submit Request", bgcolor="#DC2626", color="white", on_click=submit_refill)
            ]
        )
        page.dialog = dlg_refill
        dlg_refill.open = True
        page.update()

    # ==================== TAB 1: LIVE ORDERS ====================
    def build_sales_tab():
        sales_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        def mark_fulfilled(order_id: str):
            try:
                res = httpx.patch(f"{API_BASE_URL}/admin/orders/{order_id}/status", json={"status": "Fulfilled"}, timeout=4)
                if res.status_code == 200:
                    show_toast("Order Fulfilled & Stock Deducted!")
                    fetch_all_orders()
                    fetch_all_products()
                    render_current_tab()
            except Exception as err:
                show_toast(f"Failed: {err}", is_error=True)

        if not orders_data:
            sales_column.controls.append(
                ft.Container(
                    alignment=ft.alignment.center, padding=40,
                    content=ft.Column([
                        ft.Icon(ft.icons.RECEIPT_LONG_OUTLINED, size=48, color="#9CA3AF"),
                        ft.Text("No orders placed yet.", size=14, color="#6B7280")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
        else:
            for ord_data in orders_data:
                status = ord_data.get("status", "Pending PIN")
                status_bg = "#25D366" if status == "Paid" else ("#2563EB" if status == "Fulfilled" else "#DC2626")
                receipt = ord_data.get("receipt_number") or "None"
                phone = ord_data.get("customer_phone") or "N/A"
                total_val = float(ord_data.get("total_amount") or ord_data.get("total") or 0)
                db_id = ord_data.get("id")
                order_date_str = format_order_date(ord_data.get("created_at", ""))
                order_ref = ord_data.get("order_reference", "REF")
                items = ord_data.get("items", []) or []

                items_preview = ", ".join([f"{i.get('name', 'Item')} (x{i.get('qty', 1)})" for i in items])

                action_buttons = []
                if phone and phone != "N/A" and "Walk-in" not in phone:
                    action_buttons.append(
                        ft.IconButton(
                            ft.icons.RECEIPT_LONG,
                            tooltip="Resend WhatsApp Receipt",
                            icon_color="#25D366",
                            icon_size=20,
                            on_click=lambda e, ph=phone, oref=order_ref, st=status, tv=total_val, itms=items: send_customer_receipt_whatsapp(ph, oref, st, tv, itms)
                        )
                    )

                if status == "Paid":
                    action_buttons.append(
                        ft.ElevatedButton(
                            "Mark Fulfilled", bgcolor="#2563EB", color="white", height=32,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                            on_click=lambda e, oid=db_id: mark_fulfilled(oid)
                        )
                    )

                sales_column.controls.append(
                    ft.Container(
                        bgcolor="#FFFFFF", border_radius=10, padding=12, border=ft.border.all(1, "#E5E7EB"),
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Text(f"#{order_ref}", weight=ft.FontWeight.BOLD, size=13, color="#121212"),
                                    ft.Container(bgcolor=status_bg, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4, content=ft.Text(status, size=9, color="white", weight=ft.FontWeight.BOLD)),
                                    ft.Text(f"Ref: {receipt}", size=11, color="#4B5563", weight=ft.FontWeight.BOLD),
                                ], spacing=6),
                                ft.Text(order_date_str, size=11, color="#9CA3AF")
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(f"Items: {items_preview}", size=12, color="#374151"),
                            ft.Row([
                                ft.Text(f"Customer: {phone} • {ord_data.get('fulfillment', 'Shop Pickup')}", size=11, color="#6B7280", expand=True),
                                ft.Text(f"KES {total_val:,.0f}", size=15, weight=ft.FontWeight.BOLD, color="#DC2626"),
                                ft.Row(action_buttons, spacing=4)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ], spacing=4)
                    )
                )

        return ft.Column([
            ft.Row([
                ft.Text("Live Orders & Dispatch", size=18, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.IconButton(ft.icons.REFRESH, icon_color="#DC2626", on_click=lambda e: (fetch_all_orders(), render_current_tab()))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=sales_column, expand=True)
        ], spacing=10, expand=True)

    # ==================== TAB 2: LEADS DESK ====================
    def build_leads_tab():
        leads_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        def toggle_takeover(lead_id: str, current_status: str):
            next_status = "pending_contact" if current_status == "human_takeover" else "human_takeover"
            try:
                res = httpx.patch(f"{API_BASE_URL}/admin/leads/{lead_id}/takeover", json={"status": next_status}, timeout=4)
                if res.status_code == 200:
                    show_toast(f"Bot {'paused' if next_status == 'human_takeover' else 'resumed'}!")
                    fetch_all_leads()
                    render_current_tab()
            except Exception as err:
                show_toast(f"Failed: {err}", is_error=True)

        for lead in leads_data:
            lead_id = lead.get("id")
            phone = str(lead.get("customer_phone") or "N/A")
            intent = str(lead.get("intent") or "inquiry").lower()
            notes = lead.get("notes") or "No specific notes."
            status = lead.get("status") or "pending_contact"
            created_at = format_order_date(lead.get("created_at", ""))
            is_human = (status == "human_takeover")
            intent_bg = "#DC2626" if intent == "hot" else ("#2563EB" if intent == "purchase" else "#6B7280")

            leads_list.controls.append(
                ft.Container(
                    bgcolor="#FFFFFF", border_radius=10, padding=12, border=ft.border.all(1, "#DC2626" if is_human else "#E5E7EB"),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Text(f"📞 {phone}", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                                ft.Container(bgcolor=intent_bg, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4, content=ft.Text(intent.upper(), size=8, color="white", weight=ft.FontWeight.BOLD)),
                                ft.Container(bgcolor="#FEF2F2" if is_human else "#F3F4F6", padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4, content=ft.Text("HUMAN TAKEOVER" if is_human else "BOT ACTIVE", size=8, weight=ft.FontWeight.BOLD, color="#DC2626" if is_human else "#4B5563")),
                            ], spacing=6),
                            ft.Text(created_at, size=10, color="#9CA3AF")
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(notes, size=11, color="#374151"),
                        ft.Row([
                            ft.Row([
                                ft.ElevatedButton("WhatsApp", icon=ft.icons.CHAT, bgcolor="#25D366", color="white", height=30, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)), on_click=lambda e, ph=phone: open_whatsapp_chat(page, ph, "Hello from AyuTech Motors!")),
                                ft.IconButton(ft.icons.CALL, icon_color="#121212", icon_size=18, on_click=lambda e, ph=phone: page.launch_url(f"tel:+{normalize_phone_kenya(ph)}"))
                            ], spacing=6),
                            ft.OutlinedButton("Resume Bot" if is_human else "Takeover Lead", icon=ft.icons.SMART_TOY if is_human else ft.icons.PERSON, style=ft.ButtonStyle(color="#2563EB" if is_human else "#DC2626", side=ft.BorderSide(1, "#2563EB" if is_human else "#DC2626")), height=30, on_click=lambda e, lid=lead_id, st=status: toggle_takeover(lid, st))
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=4)
                )
            )

        return ft.Column([
            ft.Row([
                ft.Text(f"Customer Leads ({len(leads_data)})", size=18, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.IconButton(ft.icons.REFRESH, icon_color="#DC2626", on_click=lambda e: (fetch_all_leads(), render_current_tab()))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=leads_list, expand=True)
        ], spacing=10, expand=True)

    # ==================== TAB 3: INVENTORY CATALOG ====================
    def build_inventory_tab():
        is_admin = (current_user.get("role") == "admin")
        search_inv = ft.TextField(
            hint_text="Search inventory by Part Name, Number or Category...",
            expand=True, height=40, text_size=12, prefix_icon=ft.icons.SEARCH
        )
        inv_list = ft.ListView(expand=True, spacing=6)

        def quick_stock_change(prod_id: str, new_qty: int):
            try:
                res = httpx.patch(f"{API_BASE_URL}/admin/products/{prod_id}", json={"stock_quantity": max(0, new_qty)}, timeout=4)
                if res.status_code in [200, 204]:
                    fetch_all_products()
                    render_inventory_rows(search_inv.value or "")
            except Exception as err:
                show_toast(f"Failed: {err}", is_error=True)

        def render_inventory_rows(query: str = ""):
            inv_list.controls.clear()
            q = query.strip().lower()
            filtered = [
                p for p in products_data
                if q in str(p.get("name", "")).lower() 
                or q in str(p.get("part_number", "")).lower() 
                or q in str(p.get("category", "")).lower()
            ] if q else products_data

            for p in filtered:
                pid = str(p.get("id"))
                pn = p.get("part_number") or "N/A"
                current_qty = int(p.get("stock_quantity", 0) or 0)
                stock_color = "#DC2626" if current_qty <= 2 else "#16A34A"
                sup_name = p.get("supplier_name", "Direct") or "Direct"
                buy_p = float(p.get("buying_price", 0) or 0)
                sell_p = float(p.get("price", 0) or 0)

                action_buttons = []
                if is_admin:
                    action_buttons.extend([
                        ft.IconButton(ft.icons.REMOVE_CIRCLE_OUTLINE, icon_color="#DC2626", icon_size=18, tooltip="Reduce (-)", on_click=lambda e, i=pid, q=current_qty: quick_stock_change(i, q - 1)),
                        ft.IconButton(ft.icons.ADD_CIRCLE_OUTLINE, icon_color="#25D366", icon_size=18, tooltip="Restock (+)", on_click=lambda e, i=pid, q=current_qty: quick_stock_change(i, q + 1)),
                        ft.IconButton(ft.icons.EDIT_OUTLINED, icon_color="#2563EB", icon_size=18, tooltip="Edit", on_click=lambda e, prod=p: open_edit_product_dialog(prod))
                    ])
                else:
                    action_buttons.extend([
                        ft.IconButton(ft.icons.ADD_CIRCLE_OUTLINE, icon_color="#25D366", icon_size=18, tooltip="Restock (+)", on_click=lambda e, i=pid, q=current_qty: quick_stock_change(i, q + 1)),
                        ft.IconButton(ft.icons.OUTBOX_OUTLINED, icon_color="#DC2626", icon_size=18, tooltip="Request Refill", on_click=lambda e, prod=p: open_refill_dialog(prod)),
                        ft.IconButton(ft.icons.EDIT_OUTLINED, icon_color="#2563EB", icon_size=18, tooltip="Edit Info", on_click=lambda e, prod=p: open_edit_product_dialog(prod))
                    ])

                admin_pricing_text = f"Cost: KES {buy_p:,.0f} • " if is_admin else ""

                inv_list.controls.append(
                    ft.Container(
                        bgcolor="#FFFFFF",
                        border_radius=8,
                        padding=10,
                        border=ft.border.all(1, "#E5E7EB"),
                        content=ft.Row([
                            ft.Column([
                                ft.Row([
                                    ft.Text(p.get("name", ""), size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                                    ft.Container(bgcolor="#F3F4F6", padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4, content=ft.Text(p.get("category", "General"), size=9, color="#4B5563")),
                                    ft.Text(f"PN: {pn}", size=11, color="#6B7280", weight=ft.FontWeight.BOLD),
                                ], spacing=8),
                                ft.Text(f"{admin_pricing_text}Retail: KES {sell_p:,.0f} • Supplier: {sup_name}", size=11, color="#374151"),
                            ], expand=True, spacing=3),
                            ft.Row([
                                ft.Container(
                                    bgcolor="#FEF2F2" if current_qty <= 2 else "#F0FDF4",
                                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                    border_radius=6,
                                    border=ft.border.all(1, "#FECACA" if current_qty <= 2 else "#BBF7D0"),
                                    content=ft.Text(f"Stock: {current_qty}", size=11, weight=ft.FontWeight.BOLD, color=stock_color)
                                ),
                                ft.Row(action_buttons, spacing=2)
                            ], spacing=6)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    )
                )

            try:
                inv_list.update()
            except Exception:
                pass

        search_inv.on_change = lambda e: render_inventory_rows(search_inv.value or "")
        render_inventory_rows()

        return ft.Column([
            ft.Row([
                ft.Text(f"Live Inventory ({len(products_data)})", size=18, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.ElevatedButton("Add Part", icon=ft.icons.ADD, bgcolor="#DC2626", color="white", height=32, on_click=open_add_product_dialog)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            search_inv,
            inv_list
        ], spacing=10, expand=True)

    # ==================== TAB 4: MULTI-ITEM POS TERMINAL ====================
    pos_results_list = ft.ListView(expand=True, spacing=6)
    cart_table_column = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
    cart_total_display = ft.Text("KES 0", size=20, weight=ft.FontWeight.BOLD, color="#DC2626")
    cust_phone_input = ft.TextField(label="Customer Phone (e.g. 0112323814 / 254...)", value="", height=40, text_size=12)

    def update_pos_results(query: str = ""):
        pos_results_list.controls.clear()
        q = query.strip().lower()
        filtered = [
            p for p in products_data
            if q in str(p.get("name", "")).lower() or q in str(p.get("part_number", "")).lower() or q in str(p.get("category", "")).lower()
        ] if q else products_data[:20]

        for p in filtered:
            pn = p.get("part_number") or "NO-PN"
            stock = int(p.get("stock_quantity", 0) or 0)
            price = float(p.get("price", 0))

            pos_results_list.controls.append(
                ft.Container(
                    padding=8, bgcolor="#FFFFFF", border_radius=8, border=ft.border.all(1, "#E5E7EB"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(p.get("name", ""), size=12, weight=ft.FontWeight.BOLD, color="#111827"),
                            ft.Text(f"PN: {pn} • In Stock: {stock} units", size=10, color="#6B7280")
                        ], expand=True, spacing=2),
                        ft.Column([
                            ft.Text(f"KES {price:,.0f}", size=12, weight=ft.FontWeight.BOLD, color="#DC2626"),
                            ft.ElevatedButton(
                                "+ Add to Cart", bgcolor="#16A34A", color="white", height=28,
                                on_click=lambda e, itm=p: add_pos_to_cart(itm)
                            )
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )
        try:
            pos_results_list.update()
        except Exception:
            pass

    def recalculate_pos_total():
        total = sum(float(item["sale_price"]) * int(item["qty"]) for item in pos_cart)
        cart_total_display.value = f"KES {total:,.0f}"
        render_pos_cart_ui()

    def add_pos_to_cart(product: dict):
        if not product:
            show_toast("Invalid product selected.", is_error=True)
            return

        current_stock = int(product.get("stock_quantity", 0) or 0)
        if current_stock <= 0:
            show_toast(f"❌ '{product.get('name')}' is out of stock!", is_error=True)
            return

        pid = product.get("id")
        existing = next((item for item in pos_cart if item.get("product", {}).get("id") == pid), None)
        if existing:
            if existing["qty"] + 1 > current_stock:
                show_toast(f"Only {current_stock} units available in stock!", is_error=True)
                return
            existing["qty"] += 1
        else:
            pos_cart.append({
                "product": product,
                "sale_price": float(product.get("price", 0)),
                "qty": 1
            })
        recalculate_pos_total()
        product_name = str(product.get("name") or "").strip() or "Item"
        show_toast(f"Added {product_name[:18]} to cart!")

    def remove_pos_from_cart(index: int):
        if 0 <= index < len(pos_cart):
            pos_cart.pop(index)
            recalculate_pos_total()

    def render_pos_cart_ui():
        cart_table_column.controls.clear()
        if not pos_cart:
            cart_table_column.controls.append(
                ft.Container(
                    alignment=ft.alignment.center, padding=30,
                    content=ft.Column([
                        ft.Icon(ft.icons.SHOPPING_CART_OUTLINED, size=40, color="#9CA3AF"),
                        ft.Text("Cart is empty. Select parts on the left.", size=12, color="#6B7280")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
        else:
            for idx, item in enumerate(pos_cart):
                p = item["product"]
                pn = p.get("part_number") or "N/A"
                price_input = ft.TextField(value=str(int(item["sale_price"])), width=90, height=36, text_size=12, text_align=ft.TextAlign.RIGHT, content_padding=ft.padding.all(6))
                qty_input = ft.TextField(value=str(int(item["qty"])), width=50, height=36, text_size=12, text_align=ft.TextAlign.CENTER, content_padding=ft.padding.all(6))

                def on_price_change(e, itm=item, pi=price_input):
                    try:
                        raw_value = (pi.value or "").strip()
                        itm["sale_price"] = float(raw_value or 0)
                    except (TypeError, ValueError):
                        itm["sale_price"] = 0
                    total = sum(float(it["sale_price"]) * int(it["qty"]) for it in pos_cart)
                    cart_total_display.value = f"KES {total:,.0f}"
                    cart_total_display.update()

                def on_qty_change(e, itm=item, qi=qty_input):
                    try:
                        raw_value = (qi.value or "").strip()
                        itm["qty"] = max(1, int(raw_value or 1))
                    except (TypeError, ValueError):
                        itm["qty"] = 1
                    total = sum(float(it["sale_price"]) * int(it["qty"]) for it in pos_cart)
                    cart_total_display.value = f"KES {total:,.0f}"
                    cart_total_display.update()

                price_input.on_change = on_price_change
                qty_input.on_change = on_qty_change

                cart_table_column.controls.append(
                    ft.Container(
                        bgcolor="#F9FAFB", border_radius=8, padding=8, border=ft.border.all(1, "#E5E7EB"),
                        content=ft.Row([
                            ft.Column([
                                ft.Text(p.get("name", ""), size=12, weight=ft.FontWeight.BOLD, color="#121212"),
                                ft.Text(f"PN: {pn}", size=10, color="#6B7280"),
                            ], expand=True, spacing=1),
                            ft.Row([
                                price_input,
                                ft.Text("x", size=11, color="#6B7280"),
                                qty_input,
                                ft.IconButton(ft.icons.DELETE_OUTLINE, icon_color="#DC2626", icon_size=18, on_click=lambda e, i=idx: remove_pos_from_cart(i))
                            ], spacing=4)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    )
                )
        try:
            cart_table_column.update()
            cart_total_display.update()
        except Exception:
            pass

    def check_and_alert_low_stock(sold_items: list):
        low_stock_list = []
        for item in sold_items:
            p_id = item["id"]
            p_obj = next((x for x in products_data if str(x.get("id")) == str(p_id)), None)
            if p_obj:
                rem_stock = max(0, int(p_obj.get("stock_quantity", 0) or 0) - item["qty"])
                if rem_stock <= 2:
                    low_stock_list.append(f"• {item['name']} ({rem_stock} left)")

        if low_stock_list:
            alert_text = "*⚠️ AYUTECH INVENTORY ALERT: LOW STOCK*\n" + "\n".join(low_stock_list)
            open_whatsapp_chat(page, "254112323814", alert_text)

    def checkout_cart(payment_mode: str = "CASH", checkout_request_id: str | None = None):
        if not pos_cart:
            show_toast("No items in POS cart!", is_error=True)
            return

        total_val = sum(float(item["sale_price"]) * int(item["qty"]) for item in pos_cart)
        order_ref = f"{'CSH' if payment_mode == 'CASH' else 'MPS'}-{datetime.now().strftime('%H%M%S')}"
        cust_phone = (cust_phone_input.value or "").strip()
        staff_label = f"{current_user.get('name', 'Staff')} ({current_user.get('phone') or 'Counter'})"

        order_items = []
        for item in pos_cart:
            p = item["product"]
            sold_qty = int(item["qty"])
            unit_price = float(item["sale_price"])
            curr_stock = int(p.get("stock_quantity", 0) or 0)
            new_stock = max(0, curr_stock - sold_qty)

            try:
                httpx.patch(f"{API_BASE_URL}/admin/products/{p['id']}", json={"stock_quantity": new_stock}, timeout=4)
            except Exception as e:
                print(f"Stock deduct warning: {e}")

            order_items.append({
                "id": p["id"],
                "name": p.get("name"),
                "part_number": p.get("part_number", ""),
                "price": unit_price,
                "qty": sold_qty
            })

        order_payload = {
            "order_reference": order_ref,
            "customer_phone": cust_phone or f"Walk-in {payment_mode}",
            "total_amount": total_val,
            "status": "Pending PIN" if payment_mode == "M-PESA" else "Fulfilled",
            "receipt_number": f"{payment_mode}-{staff_label}",
            "fulfillment": f"Shop Counter {payment_mode} - Sold by {staff_label}",
            "items": order_items,
            "created_at": datetime.now().isoformat()
        }
        if checkout_request_id:
            order_payload["checkout_request_id"] = str(checkout_request_id)

        try:
            httpx.post(f"{API_BASE_URL}/admin/orders", json=order_payload, timeout=4)
        except Exception as e:
            print(f"Failed to record order: {e}")

        if payment_mode != "M-PESA":
            if cust_phone:
                send_customer_receipt_whatsapp(cust_phone, order_ref, payment_mode, total_val, order_items)
            check_and_alert_low_stock(order_items)
            show_toast(f"✅ {payment_mode} Sale Completed! KES {total_val:,.0f}")

        pos_cart.clear()
        recalculate_pos_total()
        fetch_all_products()
        fetch_all_orders()
        update_pos_results()

    def trigger_mpesa_stk_checkout():
        if not pos_cart:
            show_toast("No items in POS cart!", is_error=True)
            return

        cust_phone = (cust_phone_input.value or "").strip()
        clean_phone = normalize_phone_kenya(cust_phone)
        if not clean_phone or len(clean_phone) < 12:
            show_toast("Please enter a valid customer phone (e.g., 07... or 254...)", is_error=True)
            return

        total_val = sum(float(item["sale_price"]) * int(item["qty"]) for item in pos_cart)
        order_ref = f"MPS-{datetime.now().strftime('%H%M%S')}"

        show_toast(f"Sending STK prompt of KES {total_val:,.0f} to {clean_phone}...")

        try:
            res = httpx.post(
                f"{API_BASE_URL}/payments/pos-stk-push",
                json={"phone": clean_phone, "amount": total_val, "order_reference": order_ref},
                timeout=15
            )
            if res.status_code == 200:
                resp_json = res.json()
                checkout_id = resp_json.get("checkout_request_id") or resp_json.get("data", {}).get("CheckoutRequestID", "")
                show_toast("✅ STK Push sent! Awaiting customer PIN on phone.")
                checkout_cart("M-PESA", checkout_request_id=checkout_id)
            else:
                err_msg = res.json().get("detail", res.text)
                show_toast(f"STK Push Failed: {err_msg}", is_error=True)
        except Exception as err:
            show_toast(f"Network error: {err}", is_error=True)

    def open_manual_override_dialog(e=None):
        if not pos_cart:
            show_toast("Cart is empty!", is_error=True)
            return

        total_val = float(sum(float(item["sale_price"]) * int(item["qty"]) for item in pos_cart))

        method_dropdown = ft.Dropdown(
            label="Payment Channel",
            options=[
                ft.dropdown.Option("BANK_TRANSFER", "Bank Transfer / Equity / KCB"),
                ft.dropdown.Option("MANUAL_MPESA_TILL", "Alternative M-Pesa Till"),
                ft.dropdown.Option("OTHER_PAYBILL", "Alternative Paybill"),
            ],
            value="BANK_TRANSFER",
            height=42,
            text_size=12
        )
        ref_field = ft.TextField(label="Transaction / Receipt Code (Required)", height=42, text_size=12)
        notes_field = ft.TextField(label="Verification Notes (e.g. Confirmed on Manager Phone)", height=42, text_size=12)

        def submit_override(ev):
            ref_code = (ref_field.value or "").strip()
            if not ref_code:
                show_toast("Transaction reference code is mandatory!", is_error=True)
                return

            staff_label = f"{current_user.get('name', 'Staff')} ({current_user.get('phone') or 'Counter'})"
            cust_phone = (cust_phone_input.value or "Walk-in Customer").strip()
            notes_value = (notes_field.value or "").strip()

            order_items = [
                {
                    "id": str(item["product"]["id"]),
                    "name": item["product"].get("name", "Spare Part"),
                    "part_number": item["product"].get("part_number", ""),
                    "price": item["sale_price"],
                    "qty": item["qty"]
                }
                for item in pos_cart
            ]

            payload = {
                "payment_method": method_dropdown.value,
                "payment_reference": ref_code,
                "customer_phone": cust_phone,
                "total_amount": total_val,
                "items": order_items,
                "verified_by_user_id": current_user.get("phone", ""),
                "verified_by_name": staff_label,
                "notes": notes_value
            }

            try:
                res = httpx.post(f"{API_BASE_URL}/admin/orders/manual-override", json=payload, timeout=5)
                if res.status_code == 200:
                    dlg_override.open = False
                    order_ref = res.json().get("order_reference", f"MAN-{datetime.now().strftime('%H%M%S')}")

                    if cust_phone and cust_phone != "Walk-in Customer":
                        send_customer_receipt_whatsapp(cust_phone, order_ref, method_dropdown.value, total_val, order_items)

                    check_and_alert_low_stock(order_items)

                    show_toast(f"✅ Verified & Recorded: {ref_code}")
                    pos_cart.clear()
                    recalculate_pos_total()
                    fetch_all_products()
                    fetch_all_orders()
                    update_pos_results()
                else:
                    show_toast(f"Error: {res.json().get('detail', res.text)}", is_error=True)
            except Exception as err:
                show_toast(f"Connection failed: {err}", is_error=True)

        dlg_override = ft.AlertDialog(
            title=ft.Text("Manual Payment Verification", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column([
                    ft.Text(f"Total Amount to Verify: KES {total_val:,.0f}", weight=ft.FontWeight.BOLD, color="#16A34A"),
                    method_dropdown,
                    ref_field,
                    notes_field
                ], tight=True, spacing=10)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: (setattr(dlg_override, "open", False), page.update())),
                ft.ElevatedButton("Confirm & Complete Sale", bgcolor="#2563EB", color="white", on_click=submit_override)
            ]
        )
        page.dialog = dlg_override
        dlg_override.open = True
        page.update()

    def build_pos_tab():
        search_field = ft.TextField(
            hint_text="Search catalog by Part Name or Number...",
            expand=True, height=40, text_size=12, prefix_icon=ft.icons.SEARCH
        )
        search_field.on_change = lambda e: update_pos_results(search_field.value or "")
        
        update_pos_results()
        render_pos_cart_ui()

        return ft.Row([
            ft.Container(
                expand=3, bgcolor="#FFFFFF", border_radius=10, padding=14, border=ft.border.all(1, "#E5E7EB"),
                content=ft.Column([
                    ft.Text("Search & Add Items", size=16, weight=ft.FontWeight.BOLD, color="#121212"),
                    search_field,
                    pos_results_list
                ], spacing=10, expand=True)
            ),
            ft.Container(
                expand=3, bgcolor="#FFFFFF", border_radius=10, padding=14, border=ft.border.all(1, "#E5E7EB"),
                content=ft.Column([
                    ft.Row([
                        ft.Text("Active Sale Cart", size=16, weight=ft.FontWeight.BOLD, color="#121212"),
                        cart_total_display
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text("Adjust unit selling price or quantity inline:", size=11, color="#6B7280"),
                    cart_table_column,
                    cust_phone_input,
                    ft.Row([
                        ft.ElevatedButton("Cash Checkout", icon=ft.icons.PAYMENTS, bgcolor="#16A34A", color="white", height=42, expand=True, on_click=lambda e: checkout_cart("CASH")),
                        ft.ElevatedButton("M-Pesa POS", icon=ft.icons.PHONE_ANDROID, bgcolor="#2563EB", color="white", height=42, expand=True, on_click=lambda e: trigger_mpesa_stk_checkout())
                    ], spacing=8),
                    ft.ElevatedButton("Bank Transfer / Other Till Override", icon=ft.icons.ACCOUNT_BALANCE, bgcolor="#4B5563", color="white", height=38, on_click=open_manual_override_dialog)
                ], spacing=10, expand=True)
            )
        ], expand=True, spacing=12)

    # ==================== TAB 5: REFILL TRACKER ====================
    def build_refills_tab():
        is_admin = (current_user.get("role") == "admin")
        refill_cards = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        def update_refill_status(ref_id: str, new_st: str):
            try:
                res = httpx.patch(f"{API_BASE_URL}/admin/refills/{ref_id}/status", json={"status": new_st}, timeout=4)
                if res.status_code == 200:
                    show_toast(f"Status updated to {new_st}!")
                    fetch_refills()
                    fetch_all_products()
                    render_current_tab()
            except Exception as err:
                show_toast(f"Status update error: {err}", is_error=True)

        if not refills_data:
            refill_cards.controls.append(
                ft.Container(
                    alignment=ft.alignment.center, padding=40,
                    content=ft.Column([
                        ft.Icon(ft.icons.OUTBOX_OUTLINED, size=48, color="#9CA3AF"),
                        ft.Text("No active refill requests.", size=14, color="#6B7280")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
        else:
            for r in refills_data:
                ref_id = str(r.get("id"))
                st = r.get("status", "pending_approval")
                s_ph = r.get("supplier_phone", "254112323814")
                notes = r.get("notes") or "No additional notes."
                
                status_color = "#DC2626" if st == "pending_approval" else ("#2563EB" if st == "ordered_supplier" else "#16A34A")
                status_label = "PENDING APPROVAL" if st == "pending_approval" else ("ORDERED FROM SUPPLIER" if st == "ordered_supplier" else "RESTOCKED")

                p_text = f"Hello {r.get('supplier_name')}, AyuTech Motors requests an urgent order for {r.get('requested_qty')} units of {r.get('product_name')}."

                action_buttons = []
                if is_admin:
                    if st != "ordered_supplier" and st != "fulfilled":
                        action_buttons.append(
                            ft.ElevatedButton("Order WhatsApp", icon=ft.icons.SEND, bgcolor="#25D366", color="white", height=28, on_click=lambda e, ph=s_ph, q=p_text, rid=ref_id: (update_refill_status(rid, "ordered_supplier"), open_whatsapp_chat(page, ph, q)))
                        )
                    if st != "fulfilled":
                        action_buttons.append(
                            ft.ElevatedButton("Mark Restocked", icon=ft.icons.CHECK, bgcolor="#16A34A", color="white", height=28, on_click=lambda e, rid=ref_id: update_refill_status(rid, "fulfilled"))
                        )

                refill_cards.controls.append(
                    ft.Container(
                        bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#E5E7EB"),
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Text(f"{r.get('product_name')}", weight=ft.FontWeight.BOLD, size=13, color="#121212"),
                                    ft.Container(
                                        bgcolor=status_color, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4,
                                        content=ft.Text(status_label, size=8, color="white", weight=ft.FontWeight.BOLD)
                                    ),
                                    ft.Text(f"Qty: {r.get('requested_qty')}", size=12, weight=ft.FontWeight.BOLD, color="#DC2626"),
                                ], spacing=8),
                                ft.Text(format_order_date(r.get("created_at", "")), size=10, color="#9CA3AF")
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(f"Requested by: {r.get('requested_by_name')} • Supplier: {r.get('supplier_name')} ({r.get('supplier_phone')})", size=11, color="#4B5563"),
                            ft.Text(f"Notes: {notes}", size=11, color="#6B7280"),
                            ft.Row(action_buttons, alignment=ft.MainAxisAlignment.END, spacing=6) if action_buttons else ft.Container()
                        ], spacing=4)
                    )
                )

        return ft.Column([
            ft.Row([
                ft.Text(f"Refill Requests Tracker ({len(refills_data)})", size=18, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.IconButton(ft.icons.REFRESH, icon_color="#DC2626", on_click=lambda e: (fetch_refills(), render_current_tab()))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=refill_cards, expand=True)
        ], spacing=10, expand=True)

    # ==================== TAB 6: DAILY SALES ====================
    def build_daily_sales_tab():
        today_str = date.today().isoformat()
        today_orders = [
            o for o in orders_data
            if str(o.get("created_at", "")).startswith(today_str) and o.get("status") in ["Paid", "Fulfilled"]
        ]

        total_today = sum(float(o.get("total_amount") or o.get("total") or 0) for o in today_orders)
        cash_today = sum(
            float(o.get("total_amount") or o.get("total") or 0)
            for o in today_orders
            if "CASH" in str(o.get("receipt_number", "")) or "CASH" in str(o.get("fulfillment", ""))
        )
        mpesa_today = total_today - cash_today

        def send_eod_closing_report():
            if not today_orders:
                show_toast("No sales recorded today.", is_error=True)
                return

            staff_breakdown = {}
            for o in today_orders:
                attendant = o.get("receipt_number", "Unassigned")
                amt = float(o.get("total_amount") or 0)
                staff_breakdown[attendant] = staff_breakdown.get(attendant, 0) + amt

            breakdown_lines = "\n".join([f"• {k}: KES {v:,.0f}" for k, v in staff_breakdown.items()])

            eod_msg = f"""*AYUTECH MOTORS - END OF DAY REPORT*
*Date:* {date.today().strftime('%d %B %Y')}
----------------------------------------
*Total Gross Revenue:* KES {total_today:,.0f}
*Cash Drawer Balance:* KES {cash_today:,.0f}
*M-Pesa / Till / Bank:* KES {mpesa_today:,.0f}
*Total Transactions:* {len(today_orders)}
----------------------------------------
*STAFF & CHANNEL RECONCILIATION:*
{breakdown_lines}
----------------------------------------
Report generated by: {current_user.get('name')} ({current_user.get('phone') or 'Counter'})"""

            open_whatsapp_chat(page, "254112323814", eod_msg)

        sales_cards = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        for o in today_orders:
            is_cash = "CASH" in str(o.get("receipt_number", "")) or "CASH" in str(o.get("fulfillment", ""))
            badge_bg = "#16A34A" if is_cash else "#2563EB"
            badge_lbl = "CASH" if is_cash else "M-PESA / TILL"
            time_str = format_order_date(o.get("created_at", "")).split(",")[-1].strip()
            items_text = ", ".join([f"{i.get('name', 'Item')} (x{i.get('qty', 1)})" for i in o.get("items", []) or []])

            sales_cards.controls.append(
                ft.Container(
                    bgcolor="#FFFFFF", border_radius=8, padding=10, border=ft.border.all(1, "#E5E7EB"),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text(f"#{o.get('order_reference', 'REF')}", weight=ft.FontWeight.BOLD, size=12, color="#121212"),
                                ft.Container(bgcolor=badge_bg, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4, content=ft.Text(badge_lbl, size=8, color="white", weight=ft.FontWeight.BOLD)),
                                ft.Text(f"Ref: {o.get('receipt_number') or 'None'}", size=10, color="#6B7280"),
                            ], spacing=6),
                            ft.Text(items_text, size=11, color="#374151"),
                        ], expand=True, spacing=2),
                        ft.Column([
                            ft.Text(f"KES {float(o.get('total_amount', 0)):,.0f}", size=14, weight=ft.FontWeight.BOLD, color="#DC2626"),
                            ft.Text(time_str, size=10, color="#9CA3AF")
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )

        return ft.Column([
            ft.Row([
                ft.Text(f"Daily Sales Summary ({date.today().strftime('%d %B %Y')})", size=18, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.Row([
                    ft.ElevatedButton("Send EOD WhatsApp", icon=ft.icons.SEND, bgcolor="#16A34A", color="white", height=32, on_click=lambda e: send_eod_closing_report()),
                    ft.IconButton(ft.icons.REFRESH, icon_color="#DC2626", on_click=lambda e: (fetch_all_orders(), render_current_tab()))
                ], spacing=6)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([
                ft.Container(expand=True, bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#E5E7EB"), content=ft.Column([ft.Text("Total Today", size=10, color="#6B7280", weight=ft.FontWeight.BOLD), ft.Text(f"KES {total_today:,.0f}", size=16, weight=ft.FontWeight.BOLD, color="#16A34A")], spacing=2)),
                ft.Container(expand=True, bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#E5E7EB"), content=ft.Column([ft.Text("Cash Drawer", size=10, color="#6B7280", weight=ft.FontWeight.BOLD), ft.Text(f"KES {cash_today:,.0f}", size=16, weight=ft.FontWeight.BOLD, color="#121212")], spacing=2)),
                ft.Container(expand=True, bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#E5E7EB"), content=ft.Column([ft.Text("M-Pesa / Till", size=10, color="#6B7280", weight=ft.FontWeight.BOLD), ft.Text(f"KES {mpesa_today:,.0f}", size=16, weight=ft.FontWeight.BOLD, color="#2563EB")], spacing=2)),
            ], spacing=8),
            ft.Container(content=sales_cards, expand=True)
        ], spacing=10, expand=True)

    # ==================== TAB 7: ADMIN DESK & SUPPLIERS ====================
    def build_admin_desk_tab():
        if current_user.get("role") != "admin":
            return ft.Container(alignment=ft.alignment.center, content=ft.Text("Access Denied: Admin privileges required.", color="#DC2626", weight=ft.FontWeight.BOLD))

        rev = float(analytics_data.get("total_revenue", 0))
        paid_cnt = analytics_data.get("paid_orders_count", 0)
        depleted = analytics_data.get("depleted_products", [])

        kpi_row = ft.Row([
            ft.Container(expand=True, bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#E5E7EB"), content=ft.Column([ft.Text("Gross Revenue", size=10, color="#6B7280", weight=ft.FontWeight.BOLD), ft.Text(f"KES {rev:,.0f}", size=16, weight=ft.FontWeight.BOLD, color="#25D366")], spacing=2)),
            ft.Container(expand=True, bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#E5E7EB"), content=ft.Column([ft.Text("Settled Orders", size=10, color="#6B7280", weight=ft.FontWeight.BOLD), ft.Text(str(paid_cnt), size=16, weight=ft.FontWeight.BOLD, color="#121212")], spacing=2)),
            ft.Container(expand=True, bgcolor="#FFFFFF", border_radius=8, padding=12, border=ft.border.all(1, "#DC2626"), content=ft.Column([ft.Text("Low Stock", size=10, color="#DC2626", weight=ft.FontWeight.BOLD), ft.Text(f"{len(depleted)} items", size=16, weight=ft.FontWeight.BOLD, color="#DC2626")], spacing=2))
        ], spacing=8)

        suppliers_map = {}
        for p in products_data:
            s_name = p.get("supplier_name", "Direct Importer") or "Direct Importer"
            s_phone = p.get("supplier_phone", "254112323814") or "254112323814"
            if s_name not in suppliers_map:
                suppliers_map[s_name] = {"phone": s_phone, "products_count": 0, "sample_parts": []}
            suppliers_map[s_name]["products_count"] += 1
            if len(suppliers_map[s_name]["sample_parts"]) < 3:
                suppliers_map[s_name]["sample_parts"].append(p.get("name"))

        supplier_cards = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        for s_name, s_info in suppliers_map.items():
            s_ph = s_info["phone"]
            parts_preview = ", ".join(s_info["sample_parts"])
            supplier_cards.controls.append(
                ft.Container(
                    padding=10, bgcolor="#FFFFFF", border_radius=8, border=ft.border.all(1, "#E5E7EB"),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text(s_name, size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                                ft.Container(bgcolor="#EFF6FF", padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4, content=ft.Text(f"{s_info['products_count']} Parts", size=9, color="#2563EB", weight=ft.FontWeight.BOLD))
                            ], spacing=6),
                            ft.Text(f"📞 +{s_ph} • Parts: {parts_preview}...", size=10, color="#4B5563"),
                        ], expand=True),
                        ft.Row([
                            ft.IconButton(ft.icons.CHAT, icon_color="#25D366", icon_size=18, tooltip="WhatsApp", on_click=lambda e, ph=s_ph: open_whatsapp_chat(page, ph, f"Hello {s_name}, AyuTech Motors would like to inquire about parts restocking.")),
                            ft.IconButton(ft.icons.CALL, icon_color="#121212", icon_size=18, tooltip="Call", on_click=lambda e, ph=s_ph: page.launch_url(f"tel:+{normalize_phone_kenya(ph)}"))
                        ], spacing=2)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )

        return ft.Column([
            ft.Text("Executive Desk & Suppliers Management", size=18, weight=ft.FontWeight.BOLD, color="#121212"),
            kpi_row,
            ft.Container(
                expand=True, bgcolor="#FFFFFF", border_radius=10, padding=12, border=ft.border.all(1, "#E5E7EB"),
                content=ft.Column([
                    ft.Text("Suppliers Directory", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                    ft.Divider(color="#E5E7EB"),
                    supplier_cards
                ], spacing=6)
            )
        ], spacing=10, expand=True)

    # ==================== NAVIGATION CONTROLLER ====================
    def render_current_tab():
        if active_nav_index == 0:
            content_area.content = build_sales_tab()
        elif active_nav_index == 1:
            content_area.content = build_leads_tab()
        elif active_nav_index == 2:
            content_area.content = build_inventory_tab()
        elif active_nav_index == 3:
            content_area.content = build_pos_tab()
        elif active_nav_index == 4:
            content_area.content = build_refills_tab()
        elif active_nav_index == 5:
            content_area.content = build_daily_sales_tab()
        elif active_nav_index == 6:
            content_area.content = build_admin_desk_tab()
        page.update()

    def on_nav_change(e):
        nonlocal active_nav_index
        active_nav_index = int(e.control.selected_index)
        render_current_tab()

    def build_nav_destinations():
        destinations = [
            ft.NavigationRailDestination(icon=ft.icons.SHOPPING_BAG_OUTLINED, selected_icon=ft.icons.SHOPPING_BAG, label="Orders"),
            ft.NavigationRailDestination(icon=ft.icons.HEADSET_MIC_OUTLINED, selected_icon=ft.icons.HEADSET_MIC, label="Leads"),
            ft.NavigationRailDestination(icon=ft.icons.INVENTORY_2_OUTLINED, selected_icon=ft.icons.INVENTORY_2, label="Stock"),
            ft.NavigationRailDestination(icon=ft.icons.POINT_OF_SALE_OUTLINED, selected_icon=ft.icons.POINT_OF_SALE, label="POS"),
            ft.NavigationRailDestination(icon=ft.icons.OUTBOX_OUTLINED, selected_icon=ft.icons.OUTBOX, label="Refills"),
            ft.NavigationRailDestination(icon=ft.icons.ASSESSMENT_OUTLINED, selected_icon=ft.icons.ASSESSMENT, label="Daily"),
        ]
        if current_user.get("role") == "admin":
            destinations.append(
                ft.NavigationRailDestination(icon=ft.icons.ADMIN_PANEL_SETTINGS_OUTLINED, selected_icon=ft.icons.ADMIN_PANEL_SETTINGS, label="Admin")
            )
        return destinations

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=80,
        bgcolor="#121212",
        indicator_color="#DC2626",
        destinations=[],
        on_change=on_nav_change
    )

    def toggle_nav(e):
        nav_rail.visible = not nav_rail.visible
        page.update()

    user_role_badge_text = ft.Text("", size=9, weight=ft.FontWeight.BOLD, color="white")
    user_role_badge = ft.Container(
        bgcolor="#DC2626",
        padding=ft.padding.symmetric(horizontal=6, vertical=2),
        border_radius=4,
        content=user_role_badge_text
    )

    def logout_handler(e):
        current_user["name"] = "Guest"
        current_user["role"] = None
        current_user["phone"] = ""
        user_role_badge_text.value = ""
        show_login_screen()

    top_app_bar = ft.Container(
        bgcolor="#121212",
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        content=ft.Row([
            ft.Row([
                ft.IconButton(ft.icons.MENU, icon_color="white", icon_size=20, on_click=toggle_nav),
                ft.Text("AyuTech Motors", color="white", weight=ft.FontWeight.BOLD, size=15),
                user_role_badge
            ], spacing=6),
            ft.Row([
                ft.IconButton(ft.icons.SYNC, icon_color="white", icon_size=18, tooltip="Refresh Data", on_click=lambda e: refresh_all_data()),
                ft.IconButton(ft.icons.LOGOUT, icon_color="#DC2626", icon_size=18, tooltip="Logout", on_click=logout_handler)
            ], spacing=2)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # ==================== LOGIN SCREEN ====================
    identifier_field = ft.TextField(
        label="Staff Phone or Name",
        label_style=ft.TextStyle(color="#9CA3AF", size=12),
        color="white",
        width=260,
        text_size=14,
        border_color="#DC2626",
        focused_border_color="#DC2626"
    )

    pin_field = ft.TextField(
        label="4-Digit PIN",
        label_style=ft.TextStyle(color="#9CA3AF", size=12),
        color="white",
        password=True,
        can_reveal_password=True,
        width=260,
        text_align=ft.TextAlign.CENTER,
        text_size=18,
        border_color="#DC2626",
        focused_border_color="#DC2626"
    )

    def handle_pin_login(e=None):
        ident = identifier_field.value.strip() if identifier_field.value else ""
        pin_code = pin_field.value.strip() if pin_field.value else ""
        
        if not pin_code:
            show_toast("Please enter your PIN", is_error=True)
            return

        try:
            payload = {"identifier": ident, "pin": pin_code}
            res = httpx.post(f"{API_BASE_URL}/admin/auth/pin-login", json=payload, timeout=4)
            if res.status_code == 200:
                user_info = res.json().get("user", {})
                current_user["name"] = user_info.get("name", "Staff")
                current_user["role"] = user_info.get("role", "staff")
                current_user["phone"] = str(user_info.get("phone") or "").strip()

                user_role_badge_text.value = str(current_user["role"] or "").upper()
                user_role_badge.bgcolor = "#DC2626" if current_user.get("role") == "admin" else "#2563EB"
                nav_rail.destinations = build_nav_destinations()
                nav_rail.selected_index = 0
                nonlocal active_nav_index
                active_nav_index = 0

                pin_field.value = ""
                identifier_field.value = ""
                show_dashboard_screen()
                refresh_all_data()
            else:
                show_toast("Invalid Phone/Name or PIN", is_error=True)
        except Exception as err:
            show_toast(f"Connection error: {err}", is_error=True)

    identifier_field.on_submit = lambda e: pin_field.focus()
    pin_field.on_submit = handle_pin_login

    login_view = ft.Container(
        alignment=ft.alignment.center,
        expand=True,
        bgcolor="#121212",
        content=ft.Container(
            width=360,
            bgcolor="#1E1E1E",
            border_radius=12,
            padding=30,
            border=ft.border.all(1, "#333333"),
            content=ft.Column([
                ft.Icon(ft.icons.LOCK_OUTLINED, color="#DC2626", size=48),
                ft.Text("AyuTech Terminal Login", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Enter your phone or name and 4-digit PIN", size=11, color="#9CA3AF"),
                identifier_field,
                pin_field,
                ft.ElevatedButton(
                    "Unlock Portal",
                    bgcolor="#DC2626",
                    color="white",
                    width=260,
                    height=42,
                    on_click=handle_pin_login
                ),
                ft.Text("Admin: 254112323814 / 9999\nStaff: 254700000001 / 1234", size=10, color="#6B7280", text_align=ft.TextAlign.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
        )
    )

    def show_login_screen():
        main_layout.content = login_view
        page.update()

    def show_dashboard_screen():
        main_layout.content = ft.Column([
            top_app_bar,
            ft.Row([
                nav_rail,
                ft.VerticalDivider(width=1, color="#E5E7EB"),
                content_area
            ], expand=True, spacing=0)
        ], expand=True, spacing=0)
        page.update()

    def background_poller():
        while True:
            time.sleep(25)
            if current_user.get("role"):
                try:
                    fetch_all_orders()
                    fetch_all_products()
                    fetch_all_leads()
                    fetch_refills()
                    fetch_analytics()
                    if active_nav_index == 3:
                        update_pos_results()
                except Exception as poll_err:
                    print(f"Polling warning: {poll_err}")

    threading.Thread(target=background_poller, daemon=True).start()
    show_login_screen()
    page.add(main_layout)

if __name__ == "__main__":
    ft.app(target=main)