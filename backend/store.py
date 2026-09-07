import flet as ft
import httpx

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

def main(page: ft.Page):
    page.title = "Ayutech Motors Limited"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.bgcolor = "#0B0B0B"
    page.window_width = 410
    page.window_height = 800
    page.window_resizable = True

    # State variables
    cart = {}      # {p_id: {id, name, price, qty, image}}
    wishlist = {}  # {p_id: {id, name, price, image}}
    all_products = []
    current_category = "All"

    # Tab Views
    home_view = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)
    browse_view = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15, visible=False)
    cart_view = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15, visible=False)
    orders_view = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15, visible=False)
    profile_view = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15, visible=False)

    # --- Dialog Helpers ---
    def close_dlg(dlg):
        dlg.open = False
        page.update()

    def show_info_dialog(title, text):
        dlg = ft.AlertDialog(
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(text, size=13),
            actions=[ft.TextButton("Close", on_click=lambda e: close_dlg(dlg))]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def open_developer_info(e):
        dev_dialog = ft.AlertDialog(
            title=ft.Text("Support a Developer", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.CircleAvatar(radius=30, bgcolor="#DC2626", content=ft.Icon(ft.icons.CODE, color="white")),
                ft.Text("Erickson Kinyua Wachira", weight=ft.FontWeight.BOLD),
                ft.Text("Full-Stack & AI Engineer building Ayutech Motors.", size=11, color="gray"),
                ft.Text("M-Pesa Support Line: 0712345678", size=11, weight=ft.FontWeight.BOLD, color="#DC2626")
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[ft.TextButton("Close", on_click=lambda e: close_dlg(dev_dialog))]
        )
        page.dialog = dev_dialog
        dev_dialog.open = True
        page.update()

    # Floating AI Assistant Dialog
    def open_ai_assistant(e):
        ai_dialog = ft.AlertDialog(
            title=ft.Text("Ayutech AI Assistant", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text("Ask any spare part question or vehicle fitment query:", size=12, color="gray"),
                ft.TextField(label="e.g. Will this brake pad fit Hiace 7L?", multiline=True, border_color="#DC2626")
            ], tight=True),
            actions=[ft.TextButton("Close", on_click=lambda e: close_dlg(ai_dialog))]
        )
        page.dialog = ai_dialog
        ai_dialog.open = True
        page.update()

    # Safe Image Loader
    def create_product_image(img_url):
        clean_url = str(img_url).strip() if img_url else ""
        if not clean_url:
            clean_url = "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"
        return ft.Image(
            src=clean_url,
            fit=ft.ImageFit.COVER,
            error_content=ft.Icon(ft.icons.CAR_REPAIR, color="gray", size=30)
        )

    # Wishlist Handler
    def toggle_wishlist(p):
        p_id = p["id"]
        if p_id in wishlist:
            del wishlist[p_id]
            msg = f"Removed '{p['name']}' from Wishlist."
        else:
            wishlist[p_id] = p
            msg = f"Saved '{p['name']}' to Wishlist!"
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor="#DC2626")
        page.snack_bar.open = True
        render_home()
        render_browse(current_category)
        page.update()

    # Cart Handlers
    def add_to_cart(p):
        p_id = p["id"]
        if p_id in cart:
            cart[p_id]["qty"] += 1
        else:
            cart[p_id] = {
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "qty": 1,
                "image": p.get("image_url", "")
            }
        page.snack_bar = ft.SnackBar(ft.Text(f"Added '{p['name']}' to cart!"), bgcolor="#DC2626")
        page.snack_bar.open = True
        render_cart_page()
        page.update()

    def update_cart_qty(p_id, delta):
        if p_id in cart:
            cart[p_id]["qty"] += delta
            if cart[p_id]["qty"] <= 0:
                del cart[p_id]
        render_cart_page()

    # Dedicated Cart Screen View
    payment_method = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="mpesa", label="M-Pesa STK Push", fill_color="#DC2626"),
            ft.Radio(value="cash", label="Cash on Delivery", fill_color="#DC2626")
        ]),
        value="mpesa"
    )
    phone_input = ft.TextField(label="M-Pesa Phone Number", hint_text="2547XXXXXXXX", border_color="#DC2626", height=45, text_size=12)
    checkout_msg = ft.Text("", size=12, weight=ft.FontWeight.BOLD)

    def trigger_checkout(e):
        if not cart:
            return
        
        mode = payment_method.value
        phone = phone_input.value.strip() if phone_input.value else ""
        total_amt = sum(item["price"] * item["qty"] for item in cart.values())
        items_list = [{"name": item["name"], "qty": item["qty"]} for item in cart.values()]

        if mode == "mpesa" and not phone:
            checkout_msg.value = "⚠️ Please enter your M-Pesa phone number!"
            checkout_msg.color = "orange"
            page.update()
            return

        checkout_msg.value = "⏳ Processing order..."
        checkout_msg.color = "white"
        page.update()

        try:
            res = httpx.post(f"{API_BASE_URL}/payments/orders/create", json={
                "customer_phone": phone or "CASH_CUSTOMER",
                "items": items_list,
                "total_amount": total_amt
            }, timeout=10)

            if res.status_code == 200:
                order_id = res.json()["order"]["id"]
                
                if mode == "mpesa":
                    stk = httpx.post(f"{API_BASE_URL}/payments/stk-push", json={
                        "phone_number": phone, "amount": 1,
                        "callback_url": "https://washcloth-enamel-stallion.ngrok-free.dev/api/v1/payments/mpesa-callback",
                        "checkout_request_id": order_id
                    }, timeout=10)

                    if stk.status_code == 200:
                        checkout_msg.value = "📲 M-Pesa Prompt sent! Check your phone."
                        checkout_msg.color = "green"
                    else:
                        checkout_msg.value = "❌ STK Push failed."
                        checkout_msg.color = "red"
                else:
                    checkout_msg.value = "✅ Cash Order Placed! Pay on pickup at shop."
                    checkout_msg.color = "green"
                    cart.clear()
                    render_cart_page()
        except Exception as err:
            checkout_msg.value = f"❌ Error: {err}"
            checkout_msg.color = "red"
        page.update()

    def render_cart_page():
        cart_view.controls.clear()
        card_bg = "#161616" if page.theme_mode == ft.ThemeMode.DARK else "#FFFFFF"
        text_color = "white" if page.theme_mode == ft.ThemeMode.DARK else "black"

        cart_view.controls.append(
            ft.Container(padding=15, content=ft.Text("Shopping Cart", size=20, weight=ft.FontWeight.BOLD, color=text_color))
        )

        if not cart:
            cart_view.controls.append(
                ft.Container(
                    padding=40, alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.REMOVE_SHOPPING_CART, size=60, color="gray"),
                        ft.Text("Your cart is empty", size=14, color="gray")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
        else:
            items_col = ft.Column(spacing=10)
            for p_id, item in cart.items():
                items_col.controls.append(
                    ft.Container(
                        bgcolor=card_bg, border_radius=12, padding=10,
                        border=ft.border.all(1, "#DC2626" if page.theme_mode == ft.ThemeMode.LIGHT else "#262626"),
                        content=ft.Row([
                            ft.Container(
                                width=55, height=55, border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                content=create_product_image(item["image"])
                            ),
                            ft.Column([
                                ft.Text(item["name"], size=12, weight=ft.FontWeight.BOLD, color=text_color, max_lines=1),
                                ft.Text(f"KES {item['price']:,.0f}", size=12, color="#DC2626", weight=ft.FontWeight.BOLD)
                            ], expand=True),
                            ft.Row([
                                ft.IconButton(ft.icons.REMOVE, icon_size=16, icon_color="white", bgcolor="#262626", on_click=lambda e, pid=p_id: update_cart_qty(pid, -1)),
                                ft.Text(str(item["qty"]), size=13, weight=ft.FontWeight.BOLD, color=text_color),
                                ft.IconButton(ft.icons.ADD, icon_size=16, icon_color="white", bgcolor="#DC2626", on_click=lambda e, pid=p_id: update_cart_qty(pid, 1)),
                            ], spacing=2)
                        ])
                    )
                )

            total_amt = sum(item["price"] * item["qty"] for item in cart.values())
            checkout_box = ft.Container(
                bgcolor=card_bg, padding=15, border_radius=12,
                border=ft.border.all(1, "#DC2626"),
                content=ft.Column([
                    ft.Row([ft.Text("Total Amount:", color=text_color), ft.Text(f"KES {total_amt:,.2f}", size=18, color="#DC2626", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text("Select Payment Method:", size=12, color="gray"),
                    payment_method,
                    phone_input,
                    checkout_msg,
                    ft.ElevatedButton("Complete Order", bgcolor="#DC2626", color="white", width=400, height=45, on_click=trigger_checkout)
                ], spacing=10)
            )

            cart_view.controls.append(ft.Container(padding=ft.padding.symmetric(horizontal=15), content=items_col))
            cart_view.controls.append(ft.Container(padding=15, content=checkout_box))

        page.update()

    # Product Card Generator
    def build_product_card(p):
        card_bg = "#161616" if page.theme_mode == ft.ThemeMode.DARK else "#FFFFFF"
        text_color = "white" if page.theme_mode == ft.ThemeMode.DARK else "black"
        is_fav = p["id"] in wishlist

        return ft.Container(
            bgcolor=card_bg, border_radius=12, padding=10,
            border=ft.border.all(1, "#DC2626" if page.theme_mode == ft.ThemeMode.LIGHT else "#262626"),
            content=ft.Column([
                ft.Stack([
                    ft.Container(height=90, border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=create_product_image(p.get("image_url"))),
                    ft.IconButton(
                        ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER,
                        icon_color="#DC2626" if is_fav else "gray",
                        icon_size=18,
                        top=2, right=2,
                        on_click=lambda e, item=p: toggle_wishlist(item)
                    )
                ]),
                ft.Text(p["name"], size=12, weight=ft.FontWeight.BOLD, max_lines=2, color=text_color),
                ft.Row([
                    ft.Text(f"KES {p['price']:,.0f}", size=12, color="#DC2626", weight=ft.FontWeight.BOLD),
                    ft.IconButton(ft.icons.ADD_SHOPPING_CART, icon_size=16, icon_color="white", bgcolor="#DC2626", on_click=lambda e, item=p: add_to_cart(item))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    # Search Bar
    def on_search_change(e):
        query = e.control.value.strip().lower() if e.control.value else ""
        if not query:
            render_browse(current_category)
            return
        filtered = [p for p in all_products if query in p.get("name", "").lower()]
        render_browse_grid(filtered, current_category)

    search_input = ft.TextField(
        hint_text="Search auto parts, brands, filters...",
        hint_style=ft.TextStyle(color="#888888"),
        border_color="#333333", focused_border_color="#DC2626",
        bgcolor="#181818" if page.theme_mode == ft.ThemeMode.DARK else "#E9ECEF",
        height=40, text_size=13, content_padding=10,
        on_change=on_search_change
    )

    # Fetch Data
    def fetch_data():
        nonlocal all_products
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/products", timeout=10)
            if res.status_code == 200:
                all_products = res.json()
                render_home()
                render_browse("All")
        except Exception as err:
            print(f"Error loading products: {err}")

    # Render Home
    def render_home():
        home_view.controls.clear()
        text_color = "white" if page.theme_mode == ft.ThemeMode.DARK else "black"

        home_view.controls.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=15, vertical=10),
                content=ft.Container(
                    padding=15, border_radius=15,
                    gradient=ft.LinearGradient(colors=["#DC2626", "#7F1D1D"]),
                    content=ft.Column([
                        ft.Text("AYUTECH MOTORS LIMITED", size=14, color="white", weight=ft.FontWeight.BOLD),
                        ft.Text("Your one-stop shop for high-quality auto parts and lubricants on Kirinyaga Road.", size=12, color="#FCA5A5")
                    ])
                )
            )
        )
        home_view.controls.append(
            ft.Container(padding=ft.padding.symmetric(horizontal=15), content=ft.Text("🔥 Hot Deals & Best Sellers", size=16, weight=ft.FontWeight.BOLD, color=text_color))
        )

        hot_grid = ft.GridView(max_extent=180, child_aspect_ratio=0.75, spacing=10, run_spacing=10, height=360)
        for p in all_products[:4]:
            hot_grid.controls.append(build_product_card(p))
        home_view.controls.append(ft.Container(padding=ft.padding.symmetric(horizontal=15), content=hot_grid))
        page.update()

    # Render Browse
    def render_browse(category="All"):
        nonlocal current_category
        current_category = category
        prods = all_products if category == "All" else [p for p in all_products if p.get("category") == category]
        render_browse_grid(prods, category)

    def render_browse_grid(prods, category):
        browse_view.controls.clear()
        cats = ["All", "Body Parts", "Brake Parts", "Engine Parts", "Gear Parts", "Lubricants", "Service Parts", "Suspension Parts"]
        cat_pills = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)
        for c in cats:
            is_active = (c == category)
            cat_pills.controls.append(
                ft.Container(
                    content=ft.Text(c, color="white" if is_active else ("#666666" if page.theme_mode == ft.ThemeMode.LIGHT else "#AAAAAA"), size=11, weight=ft.FontWeight.BOLD),
                    bgcolor="#DC2626" if is_active else ("#E9ECEF" if page.theme_mode == ft.ThemeMode.LIGHT else "#1A1A1A"),
                    padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20,
                    data=c, on_click=lambda e: render_browse(e.control.data)
                )
            )
        browse_view.controls.append(ft.Container(padding=ft.padding.symmetric(horizontal=15), content=cat_pills))

        grid = ft.GridView(max_extent=180, child_aspect_ratio=0.75, spacing=10, run_spacing=10, expand=True)
        for p in prods:
            grid.controls.append(build_product_card(p))
        browse_view.controls.append(ft.Container(padding=ft.padding.symmetric(horizontal=15), content=grid))
        page.update()

    # Profile Modals
    def open_wishlist_modal(e):
        items_col = ft.Column(scroll=ft.ScrollMode.AUTO, height=180)
        if not wishlist:
            items_col.controls.append(ft.Text("No saved items in wishlist.", color="gray"))
        else:
            for p in wishlist.values():
                items_col.controls.append(ft.Text(f"• {p['name']} (KES {p['price']:,.0f})", size=12))

        dlg = ft.AlertDialog(
            title=ft.Text("My Saved Wishlist", weight=ft.FontWeight.BOLD),
            content=items_col,
            actions=[ft.TextButton("Close", on_click=lambda e: close_dlg(dlg))]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = "#F8F9FA"
        else:
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#0B0B0B"
        render_home()
        render_browse(current_category)
        page.update()

    # Profile Tab View
    text_color = "white" if page.theme_mode == ft.ThemeMode.DARK else "black"
    profile_view.controls = [
        ft.Container(padding=20, content=ft.Column([
            ft.CircleAvatar(radius=35, bgcolor="#DC2626", content=ft.Icon(ft.icons.PERSON, size=30, color="white")),
            ft.Text("Erickson Kinyua", size=16, weight=ft.FontWeight.BOLD, color=text_color),
            ft.Text("erickson@gmail.com | 0712345678", size=11, color="#888888"),
            ft.Divider(color="#262626"),
            ft.ListTile(leading=ft.Icon(ft.icons.FAVORITE, color="#DC2626"), title=ft.Text("My Wishlist"), on_click=open_wishlist_modal),
            ft.ListTile(leading=ft.Icon(ft.icons.BUSINESS, color="#DC2626"), title=ft.Text("Company Information"), on_click=lambda e: show_info_dialog("Ayutech Motors", "Kirinyaga Road Shop Pick-up.\nSupplying genuine Toyota, Nissan, and Mitsubishi spares.")),
            ft.ListTile(leading=ft.Icon(ft.icons.SUPPORT_AGENT, color="#DC2626"), title=ft.Text("Help & Support"), on_click=lambda e: show_info_dialog("Support Hotline", "Call/WhatsApp: +254 712 345 678")),
            ft.ListTile(leading=ft.Icon(ft.icons.CODE, color="#DC2626"), title=ft.Text("Support a Developer", color="#DC2626"), on_click=open_developer_info),
            ft.Switch(label="Dark Mode", active_color="#DC2626", value=True, on_change=toggle_theme)
        ], spacing=5))
    ]

    # Tab Switcher
    def switch_tab_index(idx):
        home_view.visible = (idx == 0)
        browse_view.visible = (idx == 1)
        cart_view.visible = (idx == 2)
        orders_view.visible = (idx == 3)
        profile_view.visible = (idx == 4)
        
        bottom_nav_bar.selected_index = idx
        if idx == 2:
            render_cart_page()
        page.update()

    def switch_tab(e):
        switch_tab_index(int(e.data))

    # Floating Bottom Bar
    bottom_nav_bar = ft.NavigationBar(
        bgcolor="transparent",
        selected_index=0,
        indicator_color="#DC2626",
        on_change=switch_tab,
        destinations=[
            ft.NavigationDestination(icon=ft.icons.HOME_OUTLINED, selected_icon=ft.icons.HOME, label="Home"),
            ft.NavigationDestination(icon=ft.icons.GRID_VIEW_OUTLINED, selected_icon=ft.icons.GRID_VIEW, label="Browse"),
            ft.NavigationDestination(icon=ft.icons.SHOPPING_CART_OUTLINED, selected_icon=ft.icons.SHOPPING_CART, label="Cart"),
            ft.NavigationDestination(icon=ft.icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.icons.RECEIPT_LONG, label="Orders"),
            ft.NavigationDestination(icon=ft.icons.PERSON_OUTLINE, selected_icon=ft.icons.PERSON, label="Profile")
        ]
    )

    bottom_nav = ft.Container(
        padding=ft.padding.only(left=15, right=15, bottom=15),
        content=ft.Container(
            border_radius=25,
            bgcolor="#121212" if page.theme_mode == ft.ThemeMode.DARK else "#FFFFFF",
            border=ft.border.all(1, "#DC2626"),
            content=bottom_nav_bar
        )
    )

    # Permanent Top Right Cart Header
    header = ft.Container(
        padding=15, bgcolor="#121212" if page.theme_mode == ft.ThemeMode.DARK else "#E9ECEF",
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.CAR_REPAIR, color="#DC2626", size=22),
                ft.Text("AYUTECH MOTORS LIMITED", size=13, weight=ft.FontWeight.BOLD, color="white" if page.theme_mode == ft.ThemeMode.DARK else "black"),
            ]),
            ft.IconButton(ft.icons.SHOPPING_CART, icon_color="#DC2626", on_click=lambda e: switch_tab_index(2))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # Floating Bottom-Right AI Assistant Button
    ai_fab = ft.FloatingActionButton(
        icon=ft.icons.AUTO_AWESOME,
        bgcolor="#DC2626",
        content=ft.Icon(ft.icons.AUTO_AWESOME, color="white", size=20),
        on_click=open_ai_assistant
    )

    main_content = ft.Column([
        header,
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=search_input),
        ft.Column([home_view, browse_view, cart_view, orders_view, profile_view], expand=True),
    ], expand=True)

    page.add(
        ft.Stack([
            main_content,
            ft.Container(content=ai_fab, right=20, bottom=90),
        ], expand=True),
        bottom_nav
    )

    fetch_data()

if __name__ == "__main__":
    ft.app(target=main)