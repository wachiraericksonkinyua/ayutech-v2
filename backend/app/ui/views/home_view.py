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
                            ft.Text("No notifications yet", size=14, weight=ft.FontWeight.BOLD, color=C.body()),
                            ft.Text("Add-to-cart, orders and updates will show here.", size=11, color=C.muted(), text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                )
            else:
                for n in app_notifications[:20]:
                    rows.append(
                        ft.Container(
                            bgcolor=C.surface(), border_radius=10, padding=ft.padding.all(10),
                            border=ft.border.all(1, C.divider()),
                            content=ft.Row([
                                ft.Container(
                                    width=34, height=34, bgcolor=C.accent_soft(), border_radius=17,
                                    alignment=ft.alignment.center,
                                    content=ft.Icon(n.get("icon") or ft.icons.CIRCLE, color=C.accent(), size=17),
                                ),
                                ft.Column([
                                    ft.Text(n.get("title", "AyuTech"), size=12, weight=ft.FontWeight.BOLD, color=C.text()),
                                    ft.Text(n.get("message", ""), size=11, color=C.body(), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
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
            bgcolor=C.surface(),
            shape=ft.RoundedRectangleBorder(radius=20),
            content=ft.Container(
                width=360,
                padding=ft.padding.all(15),
                content=ft.Column([
                    ft.Row([
                        ft.Text("Notifications", size=16, weight=ft.FontWeight.BOLD, color=C.text()),
                        ft.Container(width=8),
                        ft.Container(
                            bgcolor=C.accent(), border_radius=10,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            content=ft.Text(str(len(app_notifications)), size=11, color="white", weight=ft.FontWeight.BOLD),
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Clear All", icon=ft.icons.DELETE_SWEEP,
                            style=ft.ButtonStyle(color=C.accent()),
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
                bgcolor=C.accent(), border_radius=9,
                padding=ft.padding.symmetric(horizontal=6, vertical=1),
                content=ft.Text(str(len(app_notifications)), size=10, color="white", weight=ft.FontWeight.BOLD),
            )
        return ft.Stack([
            ft.Container(
                width=40,
                height=40,
                bgcolor=C.surface(),
                border_radius=20,
                border=ft.border.all(1, C.divider()),
                shadow=C.soft_shadow(),
                alignment=ft.alignment.center,
                content=ft.IconButton(
                    ft.icons.NOTIFICATIONS_OUTLINED, icon_color=C.text(), icon_size=20,
                    on_click=open_notifications, tooltip="Notifications",
                ),
            ),
            ft.Container(badge, top=-2, right=-2) if badge else ft.Container(),
        ])

    # Location Header Bar with brand mark
    location_header = ft.Container(
        padding=ft.padding.symmetric(horizontal=15),
        content=ft.Row([
            ft.Row([
                ft.Container(
                    width=34, height=34, bgcolor=C.accent(), border_radius=12,
                    alignment=ft.alignment.center,
                    content=ft.Text("A", size=16, weight=ft.FontWeight.W_900, color="white"),
                ),
                ft.Column([
                    ft.Text("Kirinyaga Road, Nairobi", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
                    ft.Row([
                        ft.Icon(ft.icons.LOCATION_ON, size=12, color=C.accent()),
                        ft.Text("AyuTech Motors Ltd", size=10, color=C.muted()),
                    ], spacing=3),
                ], spacing=0, tight=True),
            ], spacing=10),
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
        prefix_icon=ft.icons.SEARCH,
        prefix_style=ft.TextStyle(color=C.muted(), size=16),
        bgcolor=C.surface(),
        border_radius=16,
        height=44,
        content_padding=12,
        border_color=C.input_border(),
        focused_border_color=C.accent(),
        on_submit=handle_search
    )

    search_bar = ft.Container(
        padding=ft.padding.symmetric(horizontal=15),
        content=search_input
    )

    # Gradient hero banner
    banner = ft.Container(
        margin=ft.margin.symmetric(horizontal=15),
        padding=18,
        border_radius=20,
        shadow=C.card_shadow(),
        bgcolor=C.grad_primary(),
        content=ft.Row([
            ft.Column([
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    bgcolor="#28FFFFFF",
                    border_radius=8,
                    content=ft.Text("NEW ARRIVALS", size=9, weight=ft.FontWeight.BOLD, color="white"),
                ),
                ft.Text("Genuine Toyota & Nissan\nspares in stock.", size=15, weight=ft.FontWeight.BOLD, color="white", height=1.25),
                ft.Container(height=6),
                ft.ElevatedButton(
                    "Shop Now",
                    bgcolor="white",
                    color="#B11728",
                    height=34,
                    icon=ft.icons.ARROW_FORWARD,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    on_click=lambda e: switch_tab_callback(1)
                )
            ], spacing=8, expand=True),
            ft.Icon(ft.icons.CAR_REPAIR, size=72, color="#30FFFFFF")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # Section header with accent rule
    section_header = ft.Row([
        ft.Container(width=4, height=18, bgcolor=C.accent(), border_radius=2),
        ft.Text("Featured Products", size=15, weight=ft.FontWeight.BOLD, color=C.text()),
        ft.Container(expand=True),
        ft.TextButton(
            "View all",
            style=ft.ButtonStyle(color=C.accent()),
            on_click=lambda e: switch_tab_callback(1),
        ),
    ], spacing=8)

    # Product Cards Grid
    grid = ft.GridView(max_extent=180, child_aspect_ratio=0.72, spacing=12, run_spacing=12)
    for p in all_products[:6]:
        is_fav = p["id"] in wishlist
        img_url = p.get("image_url") or "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"

        grid.controls.append(
            ft.Container(
                bgcolor=C.surface(), border_radius=18, padding=10,
                border=ft.border.all(1, C.divider()),
                shadow=C.soft_shadow(),
                on_click=lambda e, item=p: open_detail_callback(item),
                content=ft.Column([
                    ft.Stack([
                        ft.Container(
                            height=100, border_radius=14, bgcolor=C.surface_alt(),
                            alignment=ft.alignment.center, padding=5,
                            content=ft.Image(src=img_url, fit=ft.ImageFit.CONTAIN)
                        ),
                        ft.Container(
                            top=6, right=6,
                            content=ft.Container(
                                bgcolor=C.surface(), border_radius=20,
                                shadow=C.soft_shadow(),
                                content=ft.IconButton(
                                    ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER,
                                    icon_color=C.accent() if is_fav else C.muted(), icon_size=16,
                                    on_click=lambda e, item=p: update_wishlist_callback(item)
                                ),
                            ),
                        )
                    ]),
                    ft.Text(p["name"], size=12, weight=ft.FontWeight.BOLD, max_lines=2, color=C.text()),
                    ft.Row([
                        ft.Column([
                            ft.Text("AyuTech Price", size=9, color=C.muted()),
                            ft.Text(f"KES {p['price']:,.0f}", size=13, color=C.accent(), weight=ft.FontWeight.BOLD),
                        ], spacing=0, tight=True),
                        ft.Container(
                            width=32, height=32, bgcolor=C.grad_primary(), border_radius=16,
                            alignment=ft.alignment.center,
                            on_click=lambda e, item=p: update_cart_callback(item),
                            content=ft.Icon(ft.icons.ADD_SHOPPING_CART, size=15, color="white"),
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        )

    container.controls = [
        location_header,
        search_bar,
        banner,
        ft.Container(padding=ft.padding.only(left=15, right=15, top=4), content=section_header),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=grid)
    ]
    return container