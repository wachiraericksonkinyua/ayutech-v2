import flet as ft
from app.ui.state import all_products, wishlist, notifications as app_notifications
from app.ui import colors as C

def build_home_view(page: ft.Page, update_cart_callback, update_wishlist_callback, open_detail_callback, switch_tab_callback):
    container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)

    def open_notifications(e):
        def build_rows():
            rows = []
            if not app_notifications:
                rows.append(
                    ft.Container(
                        alignment=ft.alignment.center, padding=ft.padding.all(30),
                        content=ft.Column([
                            ft.Icon(ft.icons.NOTIFICATIONS_NONE, size=46, color=C.muted()),
                            ft.Text("No notifications yet", size=14, weight=ft.FontWeight.BOLD, color=C.soft()),
                            ft.Text("Add-to-cart, orders and updates will show here.", size=11, color=C.muted(), text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                )
            else:
                for n in app_notifications[:20]:
                    rows.append(
                        ft.Container(
                            bgcolor=C.surface(), border_radius=10, padding=ft.padding.all(10),
                            border=ft.border.all(1, "#EEF0F3"),
                            content=ft.Row([
                                ft.Container(
                                    width=34, height=34, bgcolor=C.accent_soft(), border_radius=17,
                                    alignment=ft.alignment.center,
                                    content=ft.Icon(n.get("icon") or ft.icons.CIRCLE, color="#DC2626", size=17),
                                ),
                                ft.Column([
                                    ft.Text(n.get("title", "AyuTech"), size=12, weight=ft.FontWeight.BOLD, color=C.text()),
                                    ft.Text(n.get("message", ""), size=11, color=C.soft(), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ], spacing=2, expand=True),
                                ft.Text(n.get("time", ""), size=10, color=C.muted()),
                            ], spacing=10),
                        )
                    )
            return rows

        def clear_all(e):
            app_notifications.clear()
            popup.content.content.controls[2].controls = build_rows()
            popup.content.content.controls[0].controls[2].value = "0"
            popup.update()

        popup = ft.AlertDialog(
            modal=False,
            bgcolor="#FFFFFF",
            shape=ft.RoundedRectangleBorder(radius=20),
            content=ft.Container(
                width=360,
                padding=ft.padding.all(15),
                content=ft.Column([
                    ft.Row([
                        ft.Text("Notifications", size=16, weight=ft.FontWeight.BOLD, color=C.text()),
                        ft.Container(width=8),
                        ft.Container(
                            bgcolor="#DC2626", border_radius=10,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            content=ft.Text(str(len(app_notifications)), size=11, color="white", weight=ft.FontWeight.BOLD),
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Clear All", icon=ft.icons.DELETE_SWEEP,
                            style=ft.ButtonStyle(color="#DC2626"),
                            on_click=clear_all,
                        ),
                    ]),
                    ft.Container(height=4),
                    ft.Column(build_rows(), spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
                ], spacing=4, tight=True),
            ),
            actions=[ft.TextButton("Close")],
        )
        popup.actions[0].on_click = lambda e: (setattr(popup, "open", False), page.update())
        page.dialog = popup
        popup.open = True
        page.update()

    def notification_bell():
        badge = None
        if app_notifications:
            badge = ft.Container(
                bgcolor="#DC2626", border_radius=9,
                padding=ft.padding.symmetric(horizontal=6, vertical=1),
                content=ft.Text(str(len(app_notifications)), size=10, color="white", weight=ft.FontWeight.BOLD),
            )
        return ft.Stack([
            ft.IconButton(
                ft.icons.NOTIFICATIONS_OUTLINED, icon_color=C.text(), bgcolor=C.surface_alt(),
                on_click=open_notifications, tooltip="Notifications",
            ),
            ft.Container(badge, top=-2, right=-2) if badge else ft.Container(),
        ])

    # Location Header Bar matching image
    location_header = ft.Container(
        padding=ft.padding.symmetric(horizontal=15),
        content=ft.Row([
            ft.Column([
                ft.Text("Location", size=10, color=C.soft()),
                ft.Row([
                    ft.Icon(ft.icons.LOCATION_ON, size=14, color="#DC2626"),
                    ft.Text("Kirinyaga Road, Nairobi", size=12, weight=ft.FontWeight.BOLD, color=C.text()),
                    ft.Icon(ft.icons.KEYBOARD_ARROW_DOWN, size=14, color=C.text())
                ])
            ]),
            notification_bell()
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    from app.ui.state import active_search_query

    def handle_search(e):
        global active_search_query
        active_search_query = search_input.value.strip() if search_input.value else ""
        switch_tab_callback(1)

    search_input = ft.TextField(
        hint_text="Search auto parts...",
        hint_style=ft.TextStyle(color=C.muted(), size=12),
        bgcolor=C.surface_alt(),
        border_radius=15,
        height=42,
        content_padding=10,
        border_color="transparent",
        focused_border_color="#DC2626",
        on_submit=handle_search
    )

    search_bar = ft.Container(
        padding=ft.padding.symmetric(horizontal=15),
        content=search_input
    )

    # Promotion Banner with working "Shop Now" button -> Navigates to Browse tab (index 1)
    banner = ft.Container(
        margin=ft.margin.symmetric(horizontal=15),
        padding=15, border_radius=20,
        bgcolor=C.surface_alt(),
        content=ft.Row([
            ft.Column([
                ft.Text("New Arrivals", size=14, weight=ft.FontWeight.BOLD, color=C.text()),
                ft.Text("Genuine Toyota & Nissan\nspares in stock.", size=11, color=C.soft()),
                ft.Container(height=5),
                ft.ElevatedButton(
                    "Shop Now", bgcolor=C.text(), color="white", height=32,
                    style=ft.ButtonStyle(overlay_color={ft.MaterialState.HOVERED: "#DC2626"}),
                    on_click=lambda e: switch_tab_callback(1)  # Switches to Browse tab
                )
            ], expand=True),
            ft.Icon(ft.icons.CAR_REPAIR, size=60, color="#DC2626")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # Product Cards Grid
    grid = ft.GridView(max_extent=180, child_aspect_ratio=0.72, spacing=12, run_spacing=12)
    for p in all_products[:6]:
        is_fav = p["id"] in wishlist
        img_url = p.get("image_url") or "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"
        
        grid.controls.append(
            ft.Container(
                bgcolor=C.surface(), border_radius=16, padding=10,
                border=ft.border.all(1, C.divider()),
                on_click=lambda e, item=p: open_detail_callback(item),
                content=ft.Column([
                    ft.Stack([
                        ft.Container(
                            height=100, border_radius=12, bgcolor="white",
                            alignment=ft.alignment.center, padding=5,
                            content=ft.Image(src=img_url, fit=ft.ImageFit.CONTAIN)
                        ),
                        ft.IconButton(
                            ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER,
                            icon_color="#DC2626" if is_fav else "#9CA3AF", icon_size=16, top=2, right=2,
                            on_click=lambda e, item=p: update_wishlist_callback(item)
                        )
                    ]),
                    ft.Text(p["name"], size=12, weight=ft.FontWeight.BOLD, max_lines=2, color=C.text()),
                    ft.Row([
                        ft.Text(f"KES {p['price']:,.0f}", size=12, color="#DC2626", weight=ft.FontWeight.BOLD),
                        ft.IconButton(
                            ft.icons.ADD_SHOPPING_CART, icon_size=14, icon_color="white", bgcolor=C.text(),
                            style=ft.ButtonStyle(overlay_color={ft.MaterialState.HOVERED: "#DC2626"}),
                            on_click=lambda e, item=p: update_cart_callback(item)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        )

    container.controls = [
        location_header,
        search_bar,
        banner,
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=ft.Text("Featured Products", size=15, weight=ft.FontWeight.BOLD, color=C.text())),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=grid)
    ]
    return container