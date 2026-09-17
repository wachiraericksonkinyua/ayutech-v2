# backend/app/ui/main_app.py

import flet as ft
import httpx
import time
from typing import cast
from app.ui.state import all_products, cart, wishlist, API_BASE_URL
from app.ui.notifications import show_top_notification
from app.ui.views.home_view import build_home_view
from app.ui.views.browse_view import build_browse_view
from app.ui.views.cart_view import build_cart_view
from app.ui.views.orders_view import build_orders_view
from app.ui.views.profile_view import build_profile_view
from app.ui.views.product_detail_view import build_product_detail_view
from app.ui.views.dashboard_view import build_dashboard_view

API_BASE_URL = "https://ayutech-v2.onrender.com/api/v1"

def build_loading_container():
    logo_url = "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech-v2/main/images/ayutech%20logo.jpg"
    return ft.Container(
        expand=True,
        bgcolor="#FFFFFF",
        alignment=ft.alignment.center,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Text("AYUTECH", size=28, weight=ft.FontWeight.BOLD, color="#DC2626"),
                    padding=10
                ),
                ft.Container(
                    content=ft.Image(
                        src=logo_url,
                        width=140,
                        height=140,
                        fit=ft.ImageFit.CONTAIN
                    ),
                    border_radius=10,
                ),
                ft.Container(height=20),
                ft.ProgressRing(width=36, height=36, stroke_width=3, color="#DC2626"),
                ft.Container(height=12),
                ft.Text("Initializing AyuTech Motors...", size=13, weight=ft.FontWeight.W_600, color="#4B5563"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
def main(page: ft.Page):
    page.title = "AyuTech Motors Limited"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#FFFFFF"

    # Set strict mobile window dimensions across Flet versions
    window = getattr(page, "window", None)
    if window is not None:
        window.width = 400
        window.height = 800
        window.min_width = 360
        window.min_height = 700
        window.resizable = True
    else:
        page.window_width = 400
        page.window_height = 800
        page.window_min_width = 360
        page.window_min_height = 700
        page.window_resizable = True

    content_area = ft.Container(expand=True, bgcolor="#FFFFFF")
    conversation_history = []

    # Show loading container immediately on startup
    content_area.content = build_loading_container()

    # def fetch_products():
    #     start_time = time.time()
    #     try:
    #         res = httpx.get(f"{API_BASE_URL}/admin/products", timeout=8)
    #         if res.status_code == 200 and len(res.json()) > 0:
    #             all_products.clear()
    #             all_products.extend(res.json())
    #     except Exception as err:
    #         print(f"Backend offline: {err}")
        
    #     # Keep splash screen visible for at least 2.5 seconds to cache remote GitHub images
    #     elapsed = time.time() - start_time
    #     if elapsed < 2.5:
    #         time.sleep(2.5 - elapsed)
            
    #     switch_tab(0)
    def fetch_products():
      start_time = time.time()
      try:
        # Switch to public /products/ endpoint
        res = httpx.get(f'{API_BASE_URL}/products/', timeout=6, follow_redirects=True)
        if res.status_code == 200 and len(res.json()) > 0:
          all_products.clear()
          all_products.extend(res.json())
      except Exception as err:
        print(f'Backend products fetch error: {err}')

      # Fallback default items so the shop is never blank
      if not all_products:
        all_products.extend([
            {
                'id': 'fallback-1',
                'name': 'Toyota 1KD Engine Air Cleaner Element',
                'price': 2500,
                'category': 'Service Parts',
                'image_url': 'https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png',
            },
            {
                'id': 'fallback-2',
                'name': 'Mazda Demio Front Shock Absorbers',
                'price': 6500,
                'category': 'Suspension Parts',
                'image_url': 'https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png',
            },
            {
                'id': 'fallback-3',
                'name': 'Heavy Duty Brake Pads Set',
                'price': 4200,
                'category': 'Brake Parts',
                'image_url': 'https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png',
            },
        ])

      elapsed = time.time() - start_time
      if elapsed < 2.0:
        time.sleep(2.0 - elapsed)

      switch_tab(0)

    def update_cart(p, qty=1):
        p_id = str(p.get("id"))
        if p_id in cart:
            cart[p_id]["qty"] += qty
            if cart[p_id]["qty"] <= 0:
                del cart[p_id]
        elif qty > 0:
            cart[p_id] = {
                "id": p_id,
                "name": p.get("name"),
                "price": float(p.get("price", 0)),
                "qty": qty,
                "image": p.get("image_url", "")
            }
        if qty > 0:
            show_top_notification(page, f"Added to cart: {p.get('name', 'Item')}", "#16A34A", ft.icons.ADD_SHOPPING_CART)
        page.update()

    def update_wishlist(p):
        p_id = str(p.get("id"))
        if p_id in wishlist:
            del wishlist[p_id]
        else:
            wishlist[p_id] = p
        switch_tab(bottom_nav_bar.selected_index)

    def change_cart_qty(p_id, qty_diff):
        if p_id in cart:
            cart[p_id]["qty"] += qty_diff
            if cart[p_id]["qty"] <= 0:
                del cart[p_id]
        switch_tab(2)

    def open_product_detail(product):
        floating_footer.visible = False
        draggable_ai.visible = False
        content_area.content = build_product_detail_view(page, product, lambda: exit_detail_view(), update_cart)
        page.update()

    def exit_detail_view():
        floating_footer.visible = True
        draggable_ai.visible = True
        switch_tab(0)

    # --- High-Contrast AI Chat Drawer with Memory & Direct Add-to-Cart ---
    def open_ai_chat(e=None):
        page_ref = page
        chat_messages = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            expand=True
        )
        user_input = ft.TextField(
            hint_text="Ask fitment (e.g., 1KD air cleaner, Demio shocks)...",
            expand=True,
            height=42,
            text_size=12,
            border_color="#DC2626",
            focused_border_color="#DC2626"
        )
        send_button = ft.IconButton(icon=ft.icons.SEND, icon_color="#DC2626")

        def make_bubble(text: str, is_user: bool, suggested_products=None):
            if is_user:
                return ft.Container(
                    alignment=ft.alignment.center_right,
                    content=ft.Container(
                        content=ft.Text(text, size=12, weight=ft.FontWeight.W_500, color="white"),
                        bgcolor="#DC2626",
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=ft.border_radius.only(top_left=10, top_right=10, bottom_left=10, bottom_right=2)
                    )
                )
            else:
                card_items = [
                    ft.Row([
                        ft.Icon(ft.icons.PRECISION_MANUFACTURING, size=14, color="#DC2626"),
                        ft.Text("AyuTech Expert", size=11, weight=ft.FontWeight.BOLD, color="#121212")
                    ], spacing=4),
                    ft.Text(text, size=12, weight=ft.FontWeight.W_500, color="#111827", selectable=True)
                ]

                if suggested_products:
                    for sp in suggested_products:
                        p_name = sp.get("name", "Auto Part")
                        p_price = float(sp.get("price", 0))

                        def make_add_handler(prod_to_add):
                            def handle_add(evt):
                                update_cart(prod_to_add, 1)
                            return handle_add

                        card_items.append(
                            ft.Container(
                                margin=ft.margin.only(top=4),
                                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                                bgcolor="white",
                                border=ft.border.all(1, "#E5E7EB"),
                                border_radius=6,
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(p_name[:24] + "..." if len(p_name) > 24 else p_name, size=10, weight=ft.FontWeight.BOLD, color="#111827"),
                                        ft.Text(f"KES {p_price:,.0f}", size=10, color="#DC2626", weight=ft.FontWeight.W_600)
                                    ], spacing=1, expand=True),
                                    ft.ElevatedButton(
                                        "Add to Cart",
                                        icon=ft.icons.ADD_SHOPPING_CART,
                                        style=ft.ButtonStyle(
                                            bgcolor="#DC2626",
                                            color="white",
                                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                        ),
                                        on_click=make_add_handler(sp)
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                            )
                        )

                return ft.Container(
                    alignment=ft.alignment.center_left,
                    content=ft.Container(
                        content=ft.Column(card_items, spacing=3),
                        bgcolor="#F3F4F6",
                        border=ft.border.all(1, "#E5E7EB"),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=ft.border_radius.only(top_left=10, top_right=10, bottom_left=2, bottom_right=10)
                    )
                )

        def scroll_to_latest():
            page_ref.update()
            chat_messages.scroll_to(offset=-1, duration=250)
            page_ref.update()

        def close_drawer(e):
            bottom_sheet.open = False
            page_ref.update()

        if not conversation_history:
            chat_messages.controls.append(
                make_bubble("Hello! I am your spare parts fitment expert. Ask me about vehicle compatibility, engine codes, or current stock.", is_user=False)
            )
        else:
            for item in conversation_history:
                chat_messages.controls.append(make_bubble(item["content"], is_user=(item["role"] == "user")))

        def send_ai_message(e_send):
            msg = user_input.value.strip() if user_input.value else ""
            if not msg:
                return

            conversation_history.append({"role": "user", "content": msg})
            chat_messages.controls.append(make_bubble(msg, is_user=True))
            user_input.value = ""
            user_input.disabled = True
            scroll_to_latest()

            suggested_prods = []
            try:
                res = httpx.post(
                    f"{API_BASE_URL}/ai/chat",
                    json={"messages": conversation_history},
                    timeout=12
                )
                if res.status_code == 200:
                    data = res.json()
                    ai_reply = data.get("reply", "No response generated.")
                    suggested_prods = data.get("products", [])
                else:
                    ai_reply = "Could not check catalog right now. Please reach us on WhatsApp."
            except Exception:
                ai_reply = "Connection timeout. Please verify backend is active."

            conversation_history.append({"role": "assistant", "content": ai_reply})
            chat_messages.controls.append(make_bubble(ai_reply, is_user=False, suggested_products=suggested_prods))
            user_input.disabled = False
            scroll_to_latest()

        send_button.on_click = send_ai_message
        user_input.on_submit = send_ai_message

        bottom_sheet = ft.BottomSheet(
            dismissible=False,
            is_scroll_controlled=True,
            content=ft.Container(
                height=380,
                padding=ft.padding.only(left=14, right=14, top=12, bottom=14),
                bgcolor="white",
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.icons.AUTO_AWESOME, color="#DC2626", size=18),
                            ft.Text("Spare Parts AI Assistant", size=14, weight=ft.FontWeight.BOLD, color="#121212")
                        ], spacing=6),
                        ft.Row([
                            ft.IconButton(
                                ft.icons.DELETE_OUTLINE,
                                icon_color="#9CA3AF",
                                icon_size=18,
                                tooltip="Clear Chat",
                                on_click=lambda e: (
                                    conversation_history.clear(),
                                    chat_messages.controls.clear(),
                                    chat_messages.controls.append(make_bubble("Chat reset. How can I help you?", False)),
                                    scroll_to_latest()
                                )
                            ),
                            ft.IconButton(
                                ft.icons.CLOSE,
                                icon_color="#9CA3AF",
                                icon_size=18,
                                tooltip="Close Assistant",
                                on_click=close_drawer
                            )
                        ], spacing=2)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(
                        content=chat_messages,
                        expand=True,
                        padding=ft.padding.only(bottom=6)
                    ),
                    ft.Row([user_input, send_button], spacing=6)
                ], spacing=8)
            )
        )
        page_ref.overlay.append(bottom_sheet)
        bottom_sheet.open = True
        scroll_to_latest()

    def switch_tab(idx: int | None):
        if idx is None:
            idx = 0

        # Check if user is trying to access protected tabs (Cart=2, Orders=3) while logged out
        import app.ui.views.profile_view as profile_mod
        from app.ui.state import current_user_id
        
        is_logged_in = profile_mod.current_logged_in_user is not None or bool(current_user_id)

        if idx in [2, 3] and not is_logged_in:
            show_top_notification(page, "🔒 Please sign in or create an account to view cart and orders.", "#DC2626", ft.icons.LOCK)
            # Force redirect to Hub / Profile tab
            idx = 4

        floating_footer.visible = True
        draggable_ai.visible = True
        bottom_nav_bar.selected_index = idx

        if idx == 0:
            content_area.content = build_home_view(page, update_cart, update_wishlist, open_product_detail, switch_tab)
        elif idx == 1:
            content_area.content = build_browse_view(page, update_cart, update_wishlist, open_product_detail)
        elif idx == 2:
            content_area.content = build_cart_view(page, change_cart_qty, switch_tab)
        elif idx == 3:
            content_area.content = build_orders_view(page)
        elif idx == 4:
            content_area.content = build_profile_view(page, switch_tab, update_cart, open_product_detail)
        elif idx == 5:
            content_area.content = build_dashboard_view(page)
        page.update()

    bottom_nav_bar = ft.NavigationBar(
        bgcolor="transparent",
        selected_index=0,
        indicator_color="#DC2626",
        on_change=lambda e: switch_tab(int(e.data)),
        destinations=[
            ft.NavigationDestination(icon=ft.icons.HOME_OUTLINED, selected_icon=ft.icons.HOME, label="Home"),
            ft.NavigationDestination(icon=ft.icons.GRID_VIEW_OUTLINED, selected_icon=ft.icons.GRID_VIEW, label="Browse"),
            ft.NavigationDestination(icon=ft.icons.SHOPPING_BAG_OUTLINED, selected_icon=ft.icons.SHOPPING_BAG, label="Cart"),
            ft.NavigationDestination(icon=ft.icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.icons.RECEIPT_LONG, label="Orders"),
            ft.NavigationDestination(icon=ft.icons.STOREFRONT_OUTLINED, selected_icon=ft.icons.STOREFRONT, label="Hub"),
        ]
    )

    floating_footer = ft.Container(
        bottom=10,
        left=15,
        right=15,
        content=ft.Container(
            bgcolor="#121212",
            border_radius=25,
            border=ft.border.all(2, "#DC2626"),
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            content=bottom_nav_bar
        )
    )

    # --- Draggable AI Floating Button ---
    ai_button_ui = ft.Container(
        width=52,
        height=52,
        bgcolor="#121212",
        border_radius=26,
        border=ft.border.all(2, "#DC2626"),
        alignment=ft.alignment.center,
        content=ft.Icon(ft.icons.AUTO_AWESOME, color="#DC2626", size=24),
        shadow=ft.BoxShadow(blur_radius=12, color="#60000000")
    )

    def on_ai_pan_update(e: ft.DragUpdateEvent):
        cur_left = draggable_ai.left if draggable_ai.left is not None else 330
        cur_top = draggable_ai.top if draggable_ai.top is not None else 620
        new_left = cur_left + e.delta_x
        new_top = cur_top + e.delta_y

        draggable_ai.left = max(10, min(340, new_left))
        draggable_ai.top = max(40, min(700, new_top))
        draggable_ai.update()

    draggable_ai = ft.GestureDetector(
        left=330,
        top=620,
        content=ai_button_ui,
        on_tap=open_ai_chat,
        on_pan_update=on_ai_pan_update
    )

    page.add(
        ft.Stack([
            content_area,
            floating_footer,
            draggable_ai
        ], expand=True)
    )

    fetch_products()

if __name__ == "__main__":
    ft.app(target=main)