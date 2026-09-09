import flet as ft
from app.ui.state import all_products, wishlist

def build_home_view(page: ft.Page, update_cart_callback, update_wishlist_callback, open_detail_callback, switch_tab_callback):
    container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)

    # Location Header Bar matching image
    location_header = ft.Container(
        padding=ft.padding.symmetric(horizontal=15),
        content=ft.Row([
            ft.Column([
                ft.Text("Location", size=10, color="#6B7280"),
                ft.Row([
                    ft.Icon(ft.icons.LOCATION_ON, size=14, color="#DC2626"),
                    ft.Text("Kirinyaga Road, Nairobi", size=12, weight=ft.FontWeight.BOLD, color="#121212"),
                    ft.Icon(ft.icons.KEYBOARD_ARROW_DOWN, size=14, color="#121212")
                ])
            ]),
            ft.IconButton(ft.icons.NOTIFICATIONS_OUTLINED, icon_color="#121212", bgcolor="#F3F4F6")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # Search Bar -> Navigates to Browse tab (index 1) on submit
    search_input = ft.TextField(
        hint_text="Search auto parts...",
        hint_style=ft.TextStyle(color="#9CA3AF", size=12),
        bgcolor="#F3F4F6",
        border_radius=15,
        height=42,
        content_padding=10,
        border_color="transparent",
        focused_border_color="#DC2626",
        on_submit=lambda e: switch_tab_callback(1)  # Switches to Browse tab
    )

    search_bar = ft.Container(
        padding=ft.padding.symmetric(horizontal=15),
        content=search_input
    )

    # Promotion Banner with working "Shop Now" button -> Navigates to Browse tab (index 1)
    banner = ft.Container(
        margin=ft.margin.symmetric(horizontal=15),
        padding=15, border_radius=20,
        bgcolor="#F3F4F6",
        content=ft.Row([
            ft.Column([
                ft.Text("New Arrivals", size=14, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.Text("Genuine Toyota & Nissan\nspares in stock.", size=11, color="#6B7280"),
                ft.Container(height=5),
                ft.ElevatedButton(
                    "Shop Now", bgcolor="#121212", color="white", height=32,
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
                bgcolor="#F9FAFB", border_radius=16, padding=10,
                border=ft.border.all(1, "#E5E7EB"),
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
                    ft.Text(p["name"], size=12, weight=ft.FontWeight.BOLD, max_lines=2, color="#121212"),
                    ft.Row([
                        ft.Text(f"KES {p['price']:,.0f}", size=12, color="#DC2626", weight=ft.FontWeight.BOLD),
                        ft.IconButton(
                            ft.icons.ADD_SHOPPING_CART, icon_size=14, icon_color="white", bgcolor="#121212",
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
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=ft.Text("Featured Products", size=15, weight=ft.FontWeight.BOLD, color="#121212")),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=grid)
    ]
    return container