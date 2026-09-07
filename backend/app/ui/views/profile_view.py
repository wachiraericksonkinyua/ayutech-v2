# app/ui/views/profile_view.py

import flet as ft
from app.ui.state import wishlist, cart

def build_profile_view(page: ft.Page, switch_tab_callback, update_cart_callback):
    def open_external_url(url: str):
        page.launch_url(url)

    # Exact Google Maps location
    MAPS_EXACT_URL = "https://maps.app.goo.gl/iqoFy4be7SWYxCuJ8"

    # Header Branding Card
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
            ft.Text(
                "Supplying genuine OEM gearboxes, transmission assemblies, brake pads, and diesel engine components.",
                size=11,
                color="#D1D5DB"
            )
        ], spacing=4)
    )

    # Store Location & Exact Route
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

    # Contact Channels
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

    # Navigation Buttons
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

    # Wishlist Items List
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

    # Developer Signature
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