# app/ui/views/cart_view.py

import flet as ft
import httpx
import datetime
from app.ui.state import cart, my_orders, API_BASE_URL, current_user_id

def format_phone_number(raw: str) -> str:
    cleaned = "".join(filter(str.isdigit, raw))
    if cleaned.startswith("0"):
        return "254" + cleaned[1:]
    elif cleaned.startswith("254"):
        return cleaned
    elif len(cleaned) == 9:
        return "254" + cleaned
    return cleaned

def build_cart_view(page: ft.Page, change_qty_callback):
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
        border_color="#DC2626",
        bgcolor="white",
        on_change=on_zone_change
    )

    phone_input = ft.TextField(
        label="M-Pesa Number for STK Push",
        hint_text="e.g. 0712345678 or 0112345678",
        border_color="#DC2626",
        bgcolor="white",
        height=45,
        text_size=13,
        visible=True
    )

    landmark_input = ft.TextField(
        label="Specific Landmark / Building / Receiver Name",
        hint_text="e.g. Next to Total Petrol Station, Gate B",
        border_color="#E5E7EB",
        bgcolor="white",
        height=45,
        text_size=12
    )

    delivery_fee_text = ft.Text("FREE (Shop Pickup)", color="#25D366", size=12, weight=ft.FontWeight.BOLD)
    delivery_container = ft.Column([zone_dropdown, landmark_input], spacing=8, visible=False)

    if not cart:
        return ft.Column([
            ft.Container(padding=15, content=ft.Text("Shopping Cart", size=20, weight=ft.FontWeight.BOLD, color="#121212")),
            ft.Container(
                padding=40, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Icon(ft.icons.REMOVE_SHOPPING_CART, size=60, color="#9CA3AF"),
                    ft.Text("Your cart is empty", size=14, color="#6B7280")
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
        ], expand=True)

    items_col = ft.Column(spacing=10)
    for p_id, item in cart.items():
        items_col.controls.append(
            ft.Container(
                bgcolor="#F9FAFB", border_radius=12, padding=10, border=ft.border.all(1, "#E5E7EB"),
                content=ft.Row([
                    ft.Container(width=50, height=50, border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=get_item_image(item.get("image"))),
                    ft.Column([
                        ft.Text(item["name"], size=12, weight=ft.FontWeight.BOLD, color="#121212", max_lines=1),
                        ft.Text(f"KES {item['price']:,.0f}", size=12, color="#DC2626", weight=ft.FontWeight.BOLD)
                    ], expand=True),
                    ft.Row([
                        ft.IconButton(ft.icons.REMOVE, icon_size=16, icon_color="white", bgcolor="#121212", on_click=lambda e, pid=p_id: change_qty_callback(pid, -1)),
                        ft.Text(str(item["qty"]), size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                        ft.IconButton(ft.icons.ADD, icon_size=16, icon_color="white", bgcolor="#121212", on_click=lambda e, pid=p_id: change_qty_callback(pid, 1)),
                    ], spacing=2)
                ])
            )
        )

    subtotal = sum(item["price"] * item["qty"] for item in cart.values())
    total_price_text = ft.Text(f"KES {subtotal:,.0f}", color="#DC2626", size=16, weight=ft.FontWeight.BOLD)

    def update_totals():
        nonlocal delivery_fee
        fee = delivery_fee if fulfillment_type == "delivery" else 0
        delivery_fee_text.value = f"KES {fee:,.0f}" if fee > 0 else "FREE (Shop Pickup)"
        delivery_fee_text.color = "#DC2626" if fee > 0 else "#25D366"
        total_price_text.value = f"KES {(subtotal + fee):,.0f}"
        page.update()

    # Fulfillment Cards
    pickup_card = ft.Container(
        border_radius=12, padding=12,
        bgcolor="#FEE2E2", border=ft.border.all(1.5, "#DC2626"),
        content=ft.Row([
            ft.Row([ft.Icon(ft.icons.STORE_OUTLINED, color="#DC2626"), ft.Text("Shop Pick-up (Kirinyaga Rd)", weight=ft.FontWeight.BOLD, color="#121212", size=13)]),
            ft.Text("FREE", color="#25D366", weight=ft.FontWeight.BOLD, size=12)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    delivery_card = ft.Container(
        border_radius=12, padding=12,
        bgcolor="#F9FAFB", border=ft.border.all(1, "#E5E7EB"),
        content=ft.Row([
            ft.Row([ft.Icon(ft.icons.TWO_WHEELER_OUTLINED, color="#121212"), ft.Text("Rider / Courier Delivery", weight=ft.FontWeight.BOLD, color="#121212", size=13)]),
            ft.Text("From KES 200", color="#6B7280", weight=ft.FontWeight.BOLD, size=12)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    def set_fulfillment(ftype):
        nonlocal fulfillment_type, delivery_fee
        fulfillment_type = ftype
        if ftype == "pickup":
            pickup_card.bgcolor = "#FEE2E2"
            pickup_card.border = ft.border.all(1.5, "#DC2626")
            delivery_card.bgcolor = "#F9FAFB"
            delivery_card.border = ft.border.all(1, "#E5E7EB")
            delivery_container.visible = False
            delivery_fee = 0
        else:
            delivery_card.bgcolor = "#FEE2E2"
            delivery_card.border = ft.border.all(1.5, "#DC2626")
            pickup_card.bgcolor = "#F9FAFB"
            pickup_card.border = ft.border.all(1, "#E5E7EB")
            delivery_container.visible = True
            delivery_fee = get_zone_fee()
        update_totals()

    pickup_card.on_click = lambda e: set_fulfillment("pickup")
    delivery_card.on_click = lambda e: set_fulfillment("delivery")

    def make_payment_row(label, icon, selected_icon, selected):
        return ft.Row([
            ft.Row([ft.Icon(icon, color="#121212" if not selected else "#DC2626"), ft.Text(label, weight=ft.FontWeight.BOLD, color="#121212", size=13)]),
            selected_icon
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    mpesa_card = ft.Container(
        border_radius=12, padding=12,
        bgcolor="#FEE2E2", border=ft.border.all(1.5, "#DC2626"),
        content=make_payment_row("M-Pesa STK Push", ft.icons.PHONE_ANDROID, ft.Icon(ft.icons.CHECK_CIRCLE, color="#DC2626", size=18), True)
    )

    cash_card = ft.Container(
        border_radius=12, padding=12,
        bgcolor="#F9FAFB", border=ft.border.all(1, "#E5E7EB"),
        content=make_payment_row("Cash on Pickup", ft.icons.PAYMENTS_OUTLINED, ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color="gray", size=18), False)
    )

    def set_payment(method):
        nonlocal selected_payment
        selected_payment = method
        if method == "mpesa":
            mpesa_card.bgcolor = "#FEE2E2"
            mpesa_card.border = ft.border.all(1.5, "#DC2626")
            mpesa_card.content = make_payment_row("M-Pesa STK Push", ft.icons.PHONE_ANDROID, ft.Icon(ft.icons.CHECK_CIRCLE, color="#DC2626", size=18), True)
            cash_card.bgcolor = "#F9FAFB"
            cash_card.border = ft.border.all(1, "#E5E7EB")
            cash_card.content = make_payment_row("Cash on Pickup", ft.icons.PAYMENTS_OUTLINED, ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color="gray", size=18), False)
            phone_input.visible = True
            checkout_btn.text = "Pay via M-PESA"
        else:
            cash_card.bgcolor = "#FEE2E2"
            cash_card.border = ft.border.all(1.5, "#DC2626")
            cash_card.content = make_payment_row("Cash on Pickup", ft.icons.PAYMENTS_OUTLINED, ft.Icon(ft.icons.CHECK_CIRCLE, color="#DC2626", size=18), True)
            mpesa_card.bgcolor = "#F9FAFB"
            mpesa_card.border = ft.border.all(1, "#E5E7EB")
            mpesa_card.content = make_payment_row("M-Pesa STK Push", ft.icons.PHONE_ANDROID, ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color="gray", size=18), False)
            phone_input.visible = False
            checkout_btn.text = "Confirm Order"
        page.update()

    mpesa_card.on_click = lambda e: set_payment("mpesa")
    cash_card.on_click = lambda e: set_payment("cash")

    def handle_checkout(e):
        raw_phone = phone_input.value.strip() if phone_input.value else ""
        formatted_phone = format_phone_number(raw_phone)

        if selected_payment == "mpesa" and (len(formatted_phone) != 12 or not formatted_phone.startswith("254")):
            page.snack_bar = ft.SnackBar(
                ft.Text("⚠️ Enter a valid Kenyan number (e.g. 0712345678 or 0112345678)"),
                bgcolor="#DC2626"
            )
            page.snack_bar.open = True
            page.update()
            return

        checkout_btn.disabled = True
        checkout_btn.text = "Sending STK Prompt..."
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

        order_payload = {
            "phone": formatted_phone if selected_payment == "mpesa" else "Cash Customer",
            "fulfillment": "Rider / Courier Delivery" if fulfillment_type == "delivery" else "Shop Pickup",
            "location": f"{zone_dropdown.value} - {landmark_input.value}" if fulfillment_type == "delivery" else "Kirinyaga Road Shop",
            "payment_method": "M-Pesa STK Push" if selected_payment == "mpesa" else "Cash on Pickup",
            "items": items_payload,
            "total": float(final_total),
            "customer_id": current_user_id or None  # Links order to the logged-in user profile
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
                page.snack_bar = ft.SnackBar(
                    ft.Text("📲 STK Prompt sent! Enter M-Pesa PIN on your phone."),
                    bgcolor="#25D366"
                )
                page.snack_bar.open = True
                change_qty_callback("dummy", 0)
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
            page.snack_bar = ft.SnackBar(
                ft.Text("✅ Order recorded! View details in Orders tab."),
                bgcolor="#25D366"
            )
            page.snack_bar.open = True
            change_qty_callback("dummy", 0)

    checkout_btn = ft.ElevatedButton(
        "Pay via M-PESA",
        bgcolor="#DC2626", color="white", width=400, height=45,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=handle_checkout
    )

    checkout_card = ft.Container(
        padding=15, bgcolor="#FFFFFF", border_radius=15, border=ft.border.all(1, "#E5E7EB"),
        content=ft.Column([
            ft.Text("Fulfillment Option", size=14, weight=ft.FontWeight.BOLD, color="#121212"),
            pickup_card,
            delivery_card,
            delivery_container,
            ft.Divider(color="#E5E7EB"),
            ft.Text("Payment Method", size=14, weight=ft.FontWeight.BOLD, color="#121212"),
            mpesa_card,
            phone_input,
            cash_card,
            ft.Divider(color="#E5E7EB"),
            ft.Text("Order Summary", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
            ft.Row([ft.Text("Subtotal", color="#6B7280", size=12), ft.Text(f"KES {subtotal:,.0f}", color="#121212", size=12, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Delivery Fee", color="#6B7280", size=12), delivery_fee_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Total", color="#121212", size=14, weight=ft.FontWeight.BOLD), total_price_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=5),
            checkout_btn
        ], spacing=8, tight=True)
    )

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        content=ft.Column([
            ft.Text("Shopping Cart", size=20, weight=ft.FontWeight.BOLD, color="#121212"),
            items_col,
            checkout_card
        ], scroll=ft.ScrollMode.AUTO, spacing=15),
        expand=True
    )