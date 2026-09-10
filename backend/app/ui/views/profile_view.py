# app/ui/views/profile_view.py

import flet as ft
from app.ui.state import wishlist, cart
import httpx
from app.ui.state import API_BASE_URL

# Temporary session state for profile view
current_logged_in_user = None


def build_auth_view(page: ft.Page, on_login_success):
    email_field = ft.TextField(label="Email", hint_text="you@example.com", width=320, keyboard_type=ft.KeyboardType.EMAIL)
    password_field = ft.TextField(label="Password", hint_text="Your password", width=320, password=True, can_reveal_password=True)
    
    is_register_mode = ft.Ref[bool]()
    is_register_mode.current = False

    title_text = ft.Text("Welcome back", size=26, weight=ft.FontWeight.BOLD, color="#121212")
    subtitle_text = ft.Text("Sign in to your AYUTECH account", size=12, color="#6B7280")
    action_btn = ft.ElevatedButton("Login", icon=ft.icons.LOGIN, bgcolor="#DC2626", color="white", height=45, width=320)
    switch_btn = ft.OutlinedButton("Create an account", icon=ft.icons.PERSON_ADD, height=45, width=320)

    def handle_submit(e):
        email = (email_field.value or "").strip()
        password = (password_field.value or "").strip()

        if not email or not password:
            page.snack_bar = ft.SnackBar(content=ft.Text("Please fill in all fields."), bgcolor="#DC2626")
            page.snack_bar.open = True
            page.update()
            return

        if "@" not in email or "." not in email:
            page.snack_bar = ft.SnackBar(content=ft.Text("Please enter a valid email address."), bgcolor="#DC2626")
            page.snack_bar.open = True
            page.update()
            return

        endpoint = "register" if is_register_mode.current else "login"
        
        try:
            res = httpx.post(f"{API_BASE_URL}/auth/{endpoint}", json={"email": email, "password": password}, timeout=10)
            data = res.json()
            if res.status_code == 200:
                page.snack_bar = ft.SnackBar(content=ft.Text(data.get("message", "Success!")), bgcolor="#16A34A")
                page.snack_bar.open = True
                page.update()
                if not is_register_mode.current:
                    on_login_success(data.get("user"))
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(data.get("detail", "Authentication failed.")), bgcolor="#DC2626")
                page.snack_bar.open = True
                page.update()
        except Exception as err:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"Connection error: {err}"), bgcolor="#DC2626")
            page.snack_bar.open = True
            page.update()

    action_btn.on_click = handle_submit

    def toggle_mode(e):
        is_register_mode.current = not is_register_mode.current
        if is_register_mode.current:
            title_text.value = "Create Account"
            subtitle_text.value = "Register to save preferences & track orders"
            action_btn.text = "Register Account"
            action_btn.icon = ft.icons.PERSON_ADD
            switch_btn.text = "Already have an account? Login"
        else:
            title_text.value = "Welcome back"
            subtitle_text.value = "Sign in to your AYUTECH account"
            action_btn.text = "Login"
            action_btn.icon = ft.icons.LOGIN
            switch_btn.text = "Create an account"
        page.update()

    switch_btn.on_click = toggle_mode

    return ft.Container(
        expand=True,
        bgcolor="#F9FAFB",
        padding=30,
        alignment=ft.alignment.center,
        content=ft.Column([
            ft.Container(
                padding=24,
                width=380,
                bgcolor="#FFFFFF",
                border_radius=16,
                border=ft.border.all(1, "#E5E7EB"),
                content=ft.Column([
                    title_text,
                    subtitle_text,
                    ft.Divider(height=20, color="#E5E7EB"),
                    email_field,
                    password_field,
                    action_btn,
                    switch_btn
                ], spacing=14)
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )


def build_profile_view(page: ft.Page, switch_tab_callback, update_cart_callback):
    def handle_logout(e):
        global current_logged_in_user
        current_logged_in_user = None
        from app.ui.state import my_orders, wishlist, current_user_id
        my_orders.clear()
        wishlist.clear()
        current_user_id = ""
        page.snack_bar = ft.SnackBar(content=ft.Text("Logged out successfully."), bgcolor="#DC2626")
        page.snack_bar.open = True
        switch_tab_callback(4)

        
    def handle_login_success(user_data):
        """Callback for successful login from the auth view."""
        global current_logged_in_user
        from app.ui.state import current_user_id, user_info
        
        if isinstance(user_data, dict):
            current_user_id = user_data.get("id", "")
            user_info["email"] = user_data.get("email", "")
        else:
            current_user_id = getattr(user_data, "id", "")
            user_info["email"] = getattr(user_data, "email", "")

        email = user_info["email"]
        
        try:
            res = httpx.get(f"{API_BASE_URL}/auth/profile", params={"email": email}, timeout=5)
            if res.status_code == 200:
                current_logged_in_user = res.json()
            else:
                current_logged_in_user = {"email": email}
        except Exception:
            current_logged_in_user = {"email": email}

        page.snack_bar = ft.SnackBar(content=ft.Text("Successfully logged in!"), bgcolor="#16A34A")
        page.snack_bar.open = True
        switch_tab_callback(4)

    if not current_logged_in_user:
        return build_auth_view(page, handle_login_success)

    def open_external_url(url: str):
        page.launch_url(url)

    MAPS_EXACT_URL = "https://maps.app.goo.gl/iqoFy4be7SWYxCuJ8"

    header_banner = ft.Container(
        padding=20,
        bgcolor="#121212",
        border_radius=12,
        border=ft.border.all(1.5, "#DC2626"),
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=44,
                    height=44,
                    bgcolor="#DC2626",
                    border_radius=8,
                    alignment=ft.alignment.center,
                    content=ft.Icon(ft.icons.PRECISION_MANUFACTURING, color="white", size=24)
                ),
                ft.Column([
                    ft.Text("AYUTECH MOTORS LIMITED", size=15, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text("Direct Importers of Heavy Duty & Japanese Auto Spares", size=10, color="#9CA3AF")
                ], spacing=2, expand=True)
            ], spacing=12),
            ft.Divider(color="#262626", height=15),
            ft.Row([
                ft.Text(f"Logged in as: {current_logged_in_user.get('email')}", size=11, color="#D1D5DB", weight=ft.FontWeight.BOLD),
                ft.TextButton("Sign Out", style=ft.ButtonStyle(color="#DC2626"), on_click=handle_logout)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=4)
    )

    location_card = ft.Container(
        padding=16,
        bgcolor="#FFFFFF",
        border_radius=12,
        border=ft.border.all(1.5, "#DC2626"),
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.LOCATION_ON_OUTLINED, color="#DC2626", size=20),
                ft.Text("Physical Store", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
            ], spacing=8),
            ft.Text("Kirinyaga Road, Nairobi CBD, Kenya", size=12, color="#374151"),
            ft.Text("Hours: Mon – Sat (07:30 – 18:00)", size=11, color="#6B7280"),
            ft.Container(height=4),
            ft.ElevatedButton(
                "Get Driving Directions",
                icon=ft.icons.DIRECTIONS,
                bgcolor="#DC2626",
                color="white",
                height=40,
                width=400,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                on_click=lambda e: open_external_url(MAPS_EXACT_URL)
            )
        ], spacing=6)
    )

    contact_card = ft.Container(
        padding=16,
        bgcolor="#FFFFFF",
        border_radius=12,
        border=ft.border.all(1.5, "#DC2626"),
        content=ft.Column([
            ft.Text("Customer Inquiries & Support", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
            ft.Row([
                ft.ElevatedButton(
                    "Call Hotline",
                    icon=ft.icons.PHONE,
                    bgcolor="#121212",
                    color="white",
                    height=38,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: open_external_url("tel:+254112323814"),
                    expand=True
                ),
                ft.ElevatedButton(
                    "WhatsApp Desk",
                    icon=ft.icons.MESSAGE_OUTLINED,
                    bgcolor="#25D366",
                    color="white",
                    height=38,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: open_external_url("https://wa.me/254112323814"),
                    expand=True
                ),
            ], spacing=8),
            ft.OutlinedButton(
                "Email: support@ayutechmotors.co.ke",
                icon=ft.icons.ALTERNATE_EMAIL,
                height=38,
                width=400,
                style=ft.ButtonStyle(
                    color="#121212",
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, "#DC2626")
                ),
                on_click=lambda e: open_external_url("mailto:ayutechmotors@gmail.com")
            )
        ], spacing=8)
    )

    shortcuts_grid = ft.Column([
        ft.Row([
            ft.ElevatedButton(
                "Track Orders",
                icon=ft.icons.LOCAL_SHIPPING_OUTLINED,
                bgcolor="#F3F4F6",
                color="#121212",
                height=42,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, "#DC2626")
                ),
                on_click=lambda e: switch_tab_callback(3),
                expand=True
            ),
            ft.ElevatedButton(
                "My Cart",
                icon=ft.icons.SHOPPING_BAG_OUTLINED,
                bgcolor="#F3F4F6",
                color="#121212",
                height=42,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, "#DC2626")
                ),
                on_click=lambda e: switch_tab_callback(2),
                expand=True
            ),
        ], spacing=8),
        ft.Row([
            ft.ElevatedButton(
                "Catalogue",
                icon=ft.icons.GRID_VIEW_OUTLINED,
                bgcolor="#F3F4F6",
                color="#121212",
                height=42,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, "#DC2626")
                ),
                on_click=lambda e: switch_tab_callback(1),
                expand=True
            ),
            ft.ElevatedButton(
                "Home Store",
                icon=ft.icons.STOREFRONT_OUTLINED,
                bgcolor="#F3F4F6",
                color="#121212",
                height=42,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, "#DC2626")
                ),
                on_click=lambda e: switch_tab_callback(0),
                expand=True
            ),
        ], spacing=8)
    ], spacing=8)

    wishlist_container = ft.Column(spacing=8)

    def render_wishlist():
        wishlist_container.controls.clear()
        if not wishlist:
            wishlist_container.controls.append(
                ft.Container(
                    padding=16,
                    bgcolor="#F9FAFB",
                    border_radius=8,
                    border=ft.border.all(1, "#E5E7EB"),
                    content=ft.Row([
                        ft.Icon(ft.icons.BOOKMARK_BORDER, color="#9CA3AF", size=20),
                        ft.Text("No saved spare parts in your wishlist.", size=11, color="#6B7280")
                    ], spacing=10)
                )
            )
            return

        for p_id, item in wishlist.items():
            wishlist_container.controls.append(
                ft.Container(
                    padding=12,
                    bgcolor="#FFFFFF",
                    border_radius=8,
                    border=ft.border.all(1, "#DC2626"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(item.get("name", "Product"), size=12, weight=ft.FontWeight.BOLD, color="#121212"),
                            ft.Text(f"KES {float(item.get('price', 0)):,.0f}", size=12, color="#DC2626", weight=ft.FontWeight.BOLD)
                        ], expand=True),
                        ft.IconButton(
                            icon=ft.icons.ADD_SHOPPING_CART,
                            icon_color="#DC2626",
                            tooltip="Add to Cart",
                            on_click=lambda e, prod=item: (
                                update_cart_callback(prod, 1),
                                page.show_snack_bar(ft.SnackBar(ft.Text("Item added to cart"), bgcolor="#121212"))
                            )
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )

    render_wishlist()

    dev_signature = ft.Container(
        padding=15,
        alignment=ft.alignment.center,
        content=ft.Column([
            ft.Text("System Engineering & Architecture by Erickson Wachira", size=10, weight=ft.FontWeight.BOLD, color="#9CA3AF"),
            ft.TextButton(
                "Technical Support & Commercial Licensing",
                style=ft.ButtonStyle(color="#DC2626"),
                on_click=lambda e: open_external_url("https://wa.me/254112323814")
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
    )

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        bgcolor="#FFFFFF",
        expand=True,
        content=ft.Column([
            ft.Text("Store Hub", size=22, weight=ft.FontWeight.BOLD, color="#121212"),
            header_banner,
            location_card,
            contact_card,
            ft.Text("Quick Access", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
            shortcuts_grid,
            ft.Text("Saved Items (Wishlist)", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
            wishlist_container,
            ft.Divider(color="#E5E7EB"),
            dev_signature
        ], scroll=ft.ScrollMode.AUTO, spacing=14)
    )