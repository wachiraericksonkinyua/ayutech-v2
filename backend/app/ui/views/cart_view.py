# app/ui/views/cart_view.py

import flet as ft
import httpx
import datetime
from app.ui.state import cart, my_orders, API_BASE_URL, current_user_id
from app.ui.notifications import notify
from app.ui import colors as C

def format_phone_number(raw: str) -> str:
    cleaned = "".join(filter(str.isdigit, raw))
    if cleaned.startswith("0"):
        return "254" + cleaned[1:]
    elif cleaned.startswith("254"):
        return cleaned
    elif len(cleaned) == 9:
        return "254" + cleaned
    return cleaned

def build_cart_view(page: ft.Page, change_qty_callback, switch_tab_callback=None):
    def get_item_image(img_url):
        clean_url = str(img_url).strip() if img_url else ""
        if not clean_url or not clean_url.startswith("http"):
            clean_url = "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"
        return ft.Image(src=clean_url, fit=ft.ImageFit.COVER, error_content=ft.Icon(ft.icons.CAR_REPAIR, color="gray", size=24))

    selected_payment = "mpesa"
    fulfillment_type = "pickup"
    delivery_fee = 0

    zone_fees = {
        "CBD & Industrial Area (KES 200)": 200,
        "Near Suburbs: Westlands/Kilimani (KES 300)": 300,
        "Outskirts: Rongai/Ruaka/Kitengela (KES 450)": 450,
        "Upcountry Parcel / Courier (KES 600)": 600,
    }

    def get_zone_fee() -> int:
        chosen = zone_dropdown.value or ""
        return zone_fees.get(chosen, 300)

    def on_zone_change(e):
        nonlocal delivery_fee
        delivery_fee = get_zone_fee()
        update_totals()

    zone_dropdown = ft.Dropdown(
        label="Select Delivery Destination",
        options=[ft.dropdown.Option(k) for k in zone_fees.keys()],
        value="Near Suburbs: Westlands/Kilimani (KES 300)",
        text_size=12,
        border_color=C.accent(),
        bgcolor=C.field(),
        on_change=on_zone_change
    )

    phone_input = ft.TextField(
        label="M-Pesa Number for STK Push",
        hint_text="e.g. 0712345678 or 0112345678",
        border_color=C.accent(),
        bgcolor=C.field(),
        height=45,
        text_size=13,
        visible=True
    )

    landmark_input = ft.TextField(
        label="Specific Landmark / Building / Receiver Name",
        hint_text="e.g. Next to Total Petrol Station, Gate B",
        border_color=C.input_border(),
        bgcolor=C.field(),
        height=45,
        text_size=12
    )

    delivery_fee_text = ft.Text("FREE (Shop Pickup)", color=C.success(), size=12, weight=ft.FontWeight.BOLD)

    saved_address_dd = ft.Dropdown(
        label="Use a saved address",
        options=[],
        text_size=12,
        border_color=C.input_border(),
        bgcolor=C.field(),
        visible=False,
        on_change=lambda e: (address_input.__setattr__("value", ""), page.update()),
    )

    address_input = ft.TextField(
        label="Delivery Address",
        hint_text="Full address: estate / building / floor",
        border_color=C.input_border(),
        bgcolor=C.field(),
        height=45,
        text_size=12,
    )

    delivery_container = ft.Column([saved_address_dd, zone_dropdown, landmark_input, address_input], spacing=8, visible=False)

    def load_saved_addresses():
        import threading
        def _go():
            try:
                if not current_user_id:
                    return
                res = httpx.get(f"{API_BASE_URL}/auth/profile/{current_user_id}", timeout=8)
                if res.status_code == 200:
                    addrs = res.json().get("addresses") or []
                    if isinstance(addrs, list) and addrs:
                        saved_address_dd.options = [ft.dropdown.Option(str(a)) for a in addrs]
                        saved_address_dd.visible = True
                        page.update()
            except Exception:
                pass
        threading.Thread(target=_go, daemon=True).start()

    if not cart:
        return ft.Column([
            ft.Container(padding=15, content=ft.Text("Shopping Cart", size=20, weight=ft.FontWeight.BOLD, color=C.text())),
            ft.Container(
                padding=40, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Icon(ft.icons.REMOVE_SHOPPING_CART, size=60, color=C.muted()),
                    ft.Text("Your cart is empty", size=14, color=C.soft())
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
        ], expand=True)

    items_col = ft.Column(spacing=10)
    for p_id, item in cart.items():
        items_col.controls.append(
            ft.Container(
                bgcolor=C.surface(), border_radius=16, padding=10,
                border=ft.border.all(1, C.divider()),
                shadow=C.soft_shadow(),
                content=ft.Row([
                    ft.Container(width=50, height=50, border_radius=10, bgcolor=C.surface_alt(),
                                 clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=get_item_image(item.get("image"))),
                    ft.Column([
                        ft.Text(item["name"], size=12, weight=ft.FontWeight.BOLD, color=C.text(), max_lines=1),
                        ft.Text(f"KES {item['price']:,.0f}", size=12, color=C.accent(), weight=ft.FontWeight.BOLD),
                        ft.Row([
                            ft.IconButton(ft.icons.REMOVE, icon_size=15, icon_color=C.text(), bgcolor=C.surface_alt(), on_click=lambda e, pid=p_id: change_qty_callback(pid, -1)),
                            ft.Text(str(item["qty"]), size=12, weight=ft.FontWeight.BOLD, color=C.text()),
                            ft.IconButton(ft.icons.ADD, icon_size=15, icon_color="white", bgcolor=C.grad_primary(), on_click=lambda e, pid=p_id: change_qty_callback(pid, 1)),
                        ], spacing=6),
                    ], expand=True, spacing=3),
                ], spacing=10)
            )
        )

    subtotal = sum(item["price"] * item["qty"] for item in cart.values())
    total_price_text = ft.Text(f"KES {subtotal:,.0f}", color=C.accent(), size=16, weight=ft.FontWeight.BOLD)

    def update_totals():
        nonlocal delivery_fee
        fee = delivery_fee if fulfillment_type == "delivery" else 0
        delivery_fee_text.value = f"KES {fee:,.0f}" if fee > 0 else "FREE (Shop Pickup)"
        delivery_fee_text.color = C.accent() if fee > 0 else C.success()
        total_price_text.value = f"KES {(subtotal + fee):,.0f}"
        page.update()

    # Fulfillment Cards
    pickup_card = ft.Container(
        border_radius=14, padding=12,
        bgcolor=C.accent_soft(), border=ft.border.all(1.5, C.accent()),
        content=ft.Row([
            ft.Row([ft.Icon(ft.icons.STORE_OUTLINED, color=C.accent()), ft.Text("Shop Pick-up (Kirinyaga Rd)", weight=ft.FontWeight.BOLD, color=C.text(), size=13)]),
            ft.Text("FREE", color=C.success(), weight=ft.FontWeight.BOLD, size=12)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    delivery_card = ft.Container(
        border_radius=14, padding=12,
        bgcolor=C.surface(), border=ft.border.all(1, C.divider()),
        content=ft.Row([
            ft.Row([ft.Icon(ft.icons.TWO_WHEELER_OUTLINED, color=C.text()), ft.Text("Rider / Courier Delivery", weight=ft.FontWeight.BOLD, color=C.text(), size=13)]),
            ft.Text("From KES 200", color=C.soft(), weight=ft.FontWeight.BOLD, size=12)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    def set_fulfillment(ftype):
        nonlocal fulfillment_type, delivery_fee
        fulfillment_type = ftype
        if ftype == "pickup":
            pickup_card.bgcolor = C.accent_soft()
            pickup_card.border = ft.border.all(1.5, C.accent())
            pickup_card.shadow = C.soft_shadow()
            delivery_card.bgcolor = C.surface()
            delivery_card.border = ft.border.all(1, C.divider())
            delivery_card.shadow = None
            delivery_container.visible = False
            delivery_fee = 0
        else:
            delivery_card.bgcolor = C.accent_soft()
            delivery_card.border = ft.border.all(1.5, C.accent())
            delivery_card.shadow = C.soft_shadow()
            pickup_card.bgcolor = C.surface()
            pickup_card.border = ft.border.all(1, C.divider())
            pickup_card.shadow = None
            delivery_container.visible = True
            delivery_fee = get_zone_fee()
        update_totals()

    pickup_card.on_click = lambda e: set_fulfillment("pickup")
    delivery_card.on_click = lambda e: set_fulfillment("delivery")

    def make_payment_row(label, icon, selected_icon, selected):
        return ft.Row([
            ft.Row([ft.Icon(icon, color=C.text() if not selected else C.accent()), ft.Text(label, weight=ft.FontWeight.BOLD, color=C.text(), size=13)]),
            selected_icon
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    mpesa_card = ft.Container(
        border_radius=14, padding=12,
        bgcolor=C.accent_soft(), border=ft.border.all(1.5, C.accent()),
        content=make_payment_row("M-Pesa STK Push", ft.icons.PHONE_ANDROID, ft.Icon(ft.icons.CHECK_CIRCLE, color=C.accent(), size=18), True)
    )

    cash_card = ft.Container(
        border_radius=14, padding=12,
        bgcolor=C.surface(), border=ft.border.all(1, C.divider()),
        content=make_payment_row("Cash on Pickup", ft.icons.PAYMENTS_OUTLINED, ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color="gray", size=18), False)
    )

    def set_payment(method):
        nonlocal selected_payment
        selected_payment = method
        if method == "mpesa":
            mpesa_card.bgcolor = C.accent_soft()
            mpesa_card.border = ft.border.all(1.5, C.accent())
            mpesa_card.shadow = C.soft_shadow()
            mpesa_card.content = make_payment_row("M-Pesa STK Push", ft.icons.PHONE_ANDROID, ft.Icon(ft.icons.CHECK_CIRCLE, color=C.accent(), size=18), True)
            cash_card.bgcolor = C.surface()
            cash_card.border = ft.border.all(1, C.divider())
            cash_card.shadow = None
            cash_card.content = make_payment_row("Cash on Pickup", ft.icons.PAYMENTS_OUTLINED, ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color="gray", size=18), False)
            phone_input.visible = True
            cta_text.value = "Pay via M-PESA"
        else:
            cash_card.bgcolor = C.accent_soft()
            cash_card.border = ft.border.all(1.5, C.accent())
            cash_card.shadow = C.soft_shadow()
            cash_card.content = make_payment_row("Cash on Pickup", ft.icons.PAYMENTS_OUTLINED, ft.Icon(ft.icons.CHECK_CIRCLE, color=C.accent(), size=18), True)
            mpesa_card.bgcolor = C.surface()
            mpesa_card.border = ft.border.all(1, C.divider())
            mpesa_card.shadow = None
            mpesa_card.content = make_payment_row("M-Pesa STK Push", ft.icons.PHONE_ANDROID, ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color="gray", size=18), False)
            phone_input.visible = False
            cta_text.value = "Confirm Order"
        page.update()

    mpesa_card.on_click = lambda e: set_payment("mpesa")
    cash_card.on_click = lambda e: set_payment("cash")

    def handle_checkout(e):
        # Lock down checkout: guests must sign in before placing an order
        import app.ui.views.profile_view as profile_mod
        is_logged_in = profile_mod.current_logged_in_user is not None or bool(current_user_id)
        if not is_logged_in:
            notify(page, "Please sign in or create an account to check out.", C.accent(), ft.icons.LOCK, title="Access Locked")
            if switch_tab_callback is not None:
                switch_tab_callback(4)
            return

        raw_phone = phone_input.value.strip() if phone_input.value else ""
        formatted_phone = format_phone_number(raw_phone)

        if selected_payment == "mpesa" and (len(formatted_phone) != 12 or not formatted_phone.startswith("254")):
            notify(page, "Enter a valid Kenyan number (e.g. 0712345678 or 0112345678)", C.accent(), ft.icons.ERROR_OUTLINE, title="Invalid Phone")
            return

        checkout_btn.on_click = None
        cta_text.value = "Sending STK Prompt..."
        page.update()

        final_delivery_fee = delivery_fee if fulfillment_type == "delivery" else 0
        final_total = subtotal + final_delivery_fee
        
        items_payload = [
            {
                "id": str(i["id"]),
                "name": str(i["name"]),
                "price": float(i["price"]),
                "qty": int(i["qty"]),
                "image": str(i.get("image", ""))
            }
            for i in cart.values()
        ]

        active_customer_id = current_user_id if current_user_id else None

        delivery_address = ""
        if fulfillment_type == "delivery":
            delivery_address = (
                (address_input.value or "").strip()
                or (saved_address_dd.value or "").strip()
                or (landmark_input.value or "").strip()
            )

        order_payload = {
            "phone": formatted_phone if selected_payment == "mpesa" else "Cash Customer",
            "fulfillment": "Rider / Courier Delivery" if fulfillment_type == "delivery" else "Shop Pickup",
            "location": f"{zone_dropdown.value} - {landmark_input.value}" if fulfillment_type == "delivery" else "Kirinyaga Road Shop",
            "delivery_address": delivery_address,
            "payment_method": "M-Pesa STK Push" if selected_payment == "mpesa" else "Cash on Pickup",
            "items": items_payload,
            "total": float(final_total),
            "customer_id": active_customer_id  # Safely passes the active user UUID
        }
        
        try:
            res = httpx.post(f"{API_BASE_URL}/orders/checkout", json=order_payload, timeout=10)
            if res.status_code in [200, 201]:
                resp_data = res.json()
                server_order_id = resp_data.get("order_id", f"AYU-{datetime.datetime.now().strftime('%M%S')}")

                new_order = {
                    "order_id": server_order_id,
                    "date": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
                    "total": final_total,
                    "status": "Pending PIN" if selected_payment == "mpesa" else "Processing",
                    "items": list(cart.values()),
                    "fulfillment": order_payload["fulfillment"],
                    "payment_method": order_payload["payment_method"]
                }
                
                my_orders.insert(0, new_order)
                cart.clear()
                notify(page, "STK Prompt sent! Enter M-Pesa PIN on your phone.", "#25D366", ft.icons.PHONE_ANDROID, title="M-Pesa Prompt")
                show_confirmation(new_order)
            else:
                raise Exception(f"Backend returned {res.status_code}")
        except Exception as err:
            fallback_order_id = f"AYU-{datetime.datetime.now().strftime('%M%S')}"
            new_order = {
                "order_id": fallback_order_id,
                "date": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
                "total": final_total,
                "status": "Pending PIN" if selected_payment == "mpesa" else "Processing",
                "items": list(cart.values()),
                "fulfillment": order_payload["fulfillment"],
                "payment_method": order_payload["payment_method"]
            }
            my_orders.insert(0, new_order)
            cart.clear()
            notify(page, "Order recorded! View details in Orders tab.", "#25D366", ft.icons.CHECK_CIRCLE, title="Order Placed")
            show_confirmation(new_order)

    def show_confirmation(order):
      cart_ref = str(order.get("order_id", "AYU-????"))
      status_text = ft.Text(order.get("status", "Pending PIN"), size=13, weight=ft.FontWeight.BOLD, color=C.warn())
      receipt_text = ft.Text("Payment not yet detected", size=12, color=C.muted())

      def _status_color(st):
        return {"Paid": C.success(), "Processing": C.info(), "Fulfilled": C.success(), "Cancelled": C.danger()}.get(st, C.warn())

      def refresh_status():
        try:
          r = httpx.get(f"{API_BASE_URL}/orders/status/{cart_ref}", timeout=10)
          if r.status_code == 200:
            data = r.json()
            st = data.get("status", "Pending PIN")
            status_text.value = st
            status_text.color = _status_color(st)
            if data.get("receipt_number"):
              receipt_text.value = f"Receipt: {data['receipt_number']}"
              receipt_text.color = "#16A34A"
            else:
              receipt_text.value = "Payment not yet detected"
              receipt_text.color = "#9CA3AF"
            page.update()
            if st == "Paid":
              notify(page, f"Order {cart_ref} is now PAID!", "#16A34A", ft.icons.CHECK_CIRCLE, title="Payment Received")
        except Exception:
          pass

      def do_refresh(e):
        notify(page, "Checking M-Pesa status...", "#3B82F6", ft.icons.SYNC, title="Status Check")
        refresh_status()

      def open_verify(e):
        code_field = ft.TextField(
            label="M-Pesa confirmation code", hint_text="e.g. QRS1234ABCD",
            text_size=13, border_color=C.accent(), bgcolor=C.field(), height=44,
        )
        close_btn = ft.TextButton("Cancel")

        def submit_code(evt):
          code = (code_field.value or "").strip()
          if not code:
            notify(page, "Enter the M-Pesa code from your SMS.", C.accent(), ft.icons.ERROR_OUTLINE, title="Missing Code")
            return
          try:
            r = httpx.post(
                f"{API_BASE_URL}/orders/verify-receipt",
                json={"order_reference": cart_ref, "receipt_number": code},
                timeout=12,
            )
            if r.status_code in [200, 201]:
              notify(page, r.json().get("message", "Payment verified!"), "#16A34A", title="Verified")
              dlg.open = False
              page.update()
              refresh_status()
            else:
              detail = "Verification failed."
              try:
                detail = r.json().get("detail", detail)
              except Exception:
                pass
              notify(page, detail, C.accent(), ft.icons.ERROR_OUTLINE, title="Verification Failed")
              refresh_status()
          except Exception as err:
            notify(page, f"Verify error: {err}", C.accent(), ft.icons.ERROR_OUTLINE, title="Verification Failed")

        verify_btn = ft.ElevatedButton("Verify Code", bgcolor=C.accent(), color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)), on_click=submit_code)
        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=C.bg(),
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Text("Verify Payment", size=16, weight=ft.FontWeight.BOLD, color=C.text()),
            content=ft.Column([
                ft.Text("Enter the confirmation code from your M-Pesa SMS for this order.", size=12, color=C.soft()),
                code_field,
            ], tight=True, spacing=8),
            actions=[close_btn, verify_btn],
        )
        close_btn.on_click = lambda ev: (setattr(dlg, "open", False), page.update())
        page.dialog = dlg
        dlg.open = True
        page.update()

      conf_column = ft.Column([
          ft.Container(
              padding=30, alignment=ft.alignment.center,
              content=ft.Column([
                  ft.Container(
                      width=76, height=76, bgcolor=C.accent_soft(), border_radius=38,
                      alignment=ft.alignment.center,
                      content=ft.Icon(ft.icons.CHECK_CIRCLE, color="#16A34A", size=44),
                  ),
                  ft.Text("Order Confirmed!", size=20, weight=ft.FontWeight.BOLD, color=C.text()),
                  ft.Text(f"Reference: {cart_ref}", size=13, weight=ft.FontWeight.BOLD, color=C.accent()),
                  ft.Text(order.get("date", ""), size=11, color=C.muted()),
              ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
          ),
          ft.Container(
              bgcolor=C.surface(), border_radius=14, padding=14, border=ft.border.all(1, C.divider()),
              content=ft.Column([
                  ft.Text("Summary", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
                  ft.Row([ft.Text("Items", size=12, color=C.soft()), ft.Text(f"{len(order.get('items') or [])}", size=12, color=C.text(), weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                  ft.Row([ft.Text("Total", size=12, color=C.soft()), ft.Text(f"KES {float(order.get('total') or 0):,.0f}", size=13, color=C.accent(), weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                  ft.Row([ft.Text("Payment", size=12, color=C.soft()), ft.Text(order.get("payment_method", ""), size=12, color=C.text(), weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                  ft.Row([ft.Text("Fulfillment", size=12, color=C.soft()), ft.Text(order.get("fulfillment", ""), size=12, color=C.text(), weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
              ], spacing=8, tight=True),
          ),
          ft.Container(
              bgcolor=C.surface(), border_radius=14, padding=14, border=ft.border.all(1, C.divider()),
              content=ft.Column([
                  ft.Text("Payment Status", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
                  status_text,
                  receipt_text,
ft.Row([
              ft.OutlinedButton("Check Status", icon=ft.icons.REFRESH, style=ft.ButtonStyle(color=C.info(), side=ft.BorderSide(1.4, C.info()), shape=ft.RoundedRectangleBorder(radius=12)), on_click=do_refresh),
              ft.ElevatedButton("Have a Code? Verify", bgcolor=C.accent(), color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)), on_click=open_verify),
          ], spacing=8),
              ], spacing=6, tight=True),
          ),
          ft.Text("An M-Pesa prompt was sent to your phone (if M-Pesa was selected). Enter your PIN, then tap Check Status.", size=11, color=C.soft()),
          ft.Row([
              ft.FilledButton("Continue Shopping", bgcolor=C.text(), color=C.bg(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)), on_click=lambda e: switch_tab_callback(0)),
              ft.OutlinedButton("View Orders", style=ft.ButtonStyle(color=C.accent(), shape=ft.RoundedRectangleBorder(radius=12)), on_click=lambda e: switch_tab_callback(3)),
          ], spacing=8),
      ], scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)

      content_col.controls.clear()
      content_col.controls.append(conf_column)
      page.update()

    cta_text = ft.Text("Pay via M-PESA", size=13, weight=ft.FontWeight.BOLD, color="white")
    checkout_btn = ft.Container(
        height=47,
        border_radius=14,
        shadow=C.soft_shadow(),
        bgcolor=C.grad_primary(),
        alignment=ft.alignment.center,
        on_click=handle_checkout,
        content=ft.Row([
            ft.Icon(ft.icons.LOCK_OUTLINE, size=16, color="white"),
            cta_text,
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=7),
    )

    checkout_card = ft.Container(
        padding=15, bgcolor=C.surface(), border_radius=18, border=ft.border.all(1, C.divider()),
        shadow=C.soft_shadow(),
        content=ft.Column([
            ft.Text("Fulfillment Option", size=14, weight=ft.FontWeight.BOLD, color=C.text()),
            pickup_card,
            delivery_card,
            delivery_container,
            ft.Divider(color=C.divider()),
            ft.Text("Payment Method", size=14, weight=ft.FontWeight.BOLD, color=C.text()),
            mpesa_card,
            phone_input,
            cash_card,
            ft.Divider(color=C.divider()),
            ft.Text("Order Summary", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
            ft.Row([ft.Text("Subtotal", color=C.soft(), size=12), ft.Text(f"KES {subtotal:,.0f}", color=C.text(), size=12, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Delivery Fee", color=C.soft(), size=12), delivery_fee_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=6, color=C.divider()),
            ft.Row([ft.Text("Total", color=C.text(), size=14, weight=ft.FontWeight.BOLD), total_price_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=5),
            checkout_btn
        ], spacing=8, tight=True)
    )

    load_saved_addresses()

    content_col = ft.Column([
        ft.Text("Shopping Cart", size=20, weight=ft.FontWeight.BOLD, color=C.text()),
        items_col,
        checkout_card
    ], scroll=ft.ScrollMode.AUTO, spacing=15)

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        content=content_col,
        expand=True
    )