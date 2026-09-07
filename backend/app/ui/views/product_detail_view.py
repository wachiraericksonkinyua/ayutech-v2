import flet as ft
from app.ui.state import wishlist

def build_product_detail_view(page: ft.Page, product: dict, back_callback, add_to_cart_callback):
    is_fav = product["id"] in wishlist

    def toggle_fav(e):
        nonlocal is_fav
        if product["id"] in wishlist:
            del wishlist[product["id"]]
            is_fav = False
        else:
            wishlist[product["id"]] = product
            is_fav = True
        fav_btn.icon = ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER
        fav_btn.icon_color = "#DC2626" if is_fav else "#121212"
        page.update()

    fav_btn = ft.IconButton(
        icon=ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER,
        icon_color="#DC2626" if is_fav else "#121212",
        on_click=toggle_fav
    )

    img_url = product.get("image_url") or "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"
    qty_val = ft.Text("1", size=14, weight=ft.FontWeight.BOLD, color="#121212")

    def update_qty(delta):
        # qty_val.value may be None; fallback to "1" to satisfy int() conversion
        current = int(qty_val.value or "1")
        new_qty = max(1, current + delta)
        qty_val.value = str(new_qty)
        page.update()

    # Call / WhatsApp Store Actions
    def call_store(e):
        page.launch_url("tel:+254712345678")

    def whatsapp_store(e):
        msg = f"Hello Ayutech Motors, I am inquiring about {product['name']} (KES {product['price']:,.0f})"
        page.launch_url(f"https://wa.me/254712345678?text={msg}")

    header_bar = ft.Container(
        padding=15,
        content=ft.Row([
            ft.IconButton(ft.icons.ARROW_BACK, icon_color="#121212", on_click=lambda e: back_callback()),
            ft.Text("Product Details", size=16, weight=ft.FontWeight.BOLD, color="#121212"),
            fav_btn
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    image_preview = ft.Container(
        height=220, border_radius=20, bgcolor="#F3F4F6", alignment=ft.alignment.center,
        padding=15, content=ft.Image(src=img_url, fit=ft.ImageFit.CONTAIN)
    )

    # Quick Action Buttons Bar (Call & WhatsApp)
    action_buttons = ft.Row([
        ft.Container(
            expand=True, bgcolor="#F3F4F6", border_radius=12, padding=10,
            on_click=call_store,
            content=ft.Row([ft.Icon(ft.icons.PHONE, size=16, color="#DC2626"), ft.Text("Call Shop", size=12, weight=ft.FontWeight.BOLD, color="#121212")], alignment=ft.MainAxisAlignment.CENTER)
        ),
        ft.Container(
            expand=True, bgcolor="#F3F4F6", border_radius=12, padding=10,
            on_click=whatsapp_store,
            content=ft.Row([ft.Icon(ft.icons.CHAT, size=16, color="#25D366"), ft.Text("WhatsApp", size=12, weight=ft.FontWeight.BOLD, color="#121212")], alignment=ft.MainAxisAlignment.CENTER)
        )
    ], spacing=10)

    # Dynamic Product Description from Database
    prod_description = product.get("description") or (
        f"Genuine {product.get('category', 'automotive')} replacement part distributed by Ayutech Motors Limited. "
        "Engineered for high durability and exact OEM fitment on Kirinyaga Road standards."
    )

    details_content = ft.Column([
        ft.Container(
            bgcolor="#FEE2E2", border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=4),
            content=ft.Text(product.get("category", "Auto Part"), size=11, color="#DC2626", weight=ft.FontWeight.BOLD)
        ),
        ft.Text(product["name"], size=18, weight=ft.FontWeight.BOLD, color="#121212"),
        action_buttons,
        ft.Text("Description & Fitment Notes", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
        ft.Text(prod_description, size=12, color="#4B5563"),
        ft.Divider(color="#E5E7EB"),
        ft.Row([
            ft.Text("Quantity:", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
            ft.Row([
                ft.IconButton(ft.icons.REMOVE, icon_size=16, icon_color="white", bgcolor="#121212", on_click=lambda e: update_qty(-1)),
                qty_val,
                ft.IconButton(ft.icons.ADD, icon_size=16, icon_color="white", bgcolor="#DC2626", on_click=lambda e: update_qty(1)),
            ], spacing=10)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    ], spacing=12)

    return ft.Column([
        header_bar,
        ft.Container(
            padding=ft.padding.symmetric(horizontal=15),
            content=ft.Column([image_preview, details_content], scroll=ft.ScrollMode.AUTO, expand=True)
        ),
        ft.Container(
            padding=15, bgcolor="white", border=ft.border.only(top=ft.BorderSide(1, "#E5E7EB")),
            content=ft.Row([
                ft.Column([
                    ft.Text("Total Price", size=11, color="#6B7280"),
                    ft.Text(f"KES {product['price']:,.0f}", size=18, weight=ft.FontWeight.BOLD, color="#DC2626")
                ]),
                ft.ElevatedButton(
                    "Add to Cart",
                    icon=ft.icons.SHOPPING_BAG,
                    bgcolor="#121212", color="white", height=45, width=170,
                    # Removed ControlState reference as it's not available in this flet version
                    style=ft.ButtonStyle(),
                    on_click=lambda e: add_to_cart_callback(product, int(qty_val.value or "1"))
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )
    ], expand=True)