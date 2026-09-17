import flet as ft
from app.ui.state import all_products, wishlist
from app.ui import colors as C

def build_browse_view(page: ft.Page, update_cart_callback, update_wishlist_callback, open_detail_callback):
    container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)

    current_cat = "All"
    current_query = ""

    grid_container = ft.Container()

    def build_product_card(p):
        is_fav = p["id"] in wishlist
        img_url = p.get("image_url") or "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"
        return ft.Container(
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

    def filter_and_render():
        prods = all_products
        if current_cat != "All":
            prods = [p for p in prods if p.get("category") == current_cat]
        if current_query:
            prods = [p for p in prods if current_query in p.get("name", "").lower()]

        grid = ft.GridView(max_extent=180, child_aspect_ratio=0.72, spacing=12, run_spacing=12)

        if not prods:
            grid_container.content = ft.Container(
                padding=40, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Icon(ft.icons.SEARCH_OFF, size=44, color=C.muted()),
                    ft.Text("No matching auto parts found.", color=C.soft(), size=13),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
            )
        else:
            for p in prods:
                grid.controls.append(build_product_card(p))
            grid_container.content = grid
        result_count.value = f"{len(prods)} spares in stock"
        page.update()

    def on_search(e):
        nonlocal current_query
        current_query = e.control.value.strip().lower() if e.control.value else ""
        filter_and_render()

    search_tf = ft.TextField(
        hint_text="Search auto parts (e.g. rack end, brake pads)...",
        hint_style=ft.TextStyle(color=C.muted(), size=12),
        prefix_icon=ft.icons.SEARCH,
        prefix_style=ft.TextStyle(color=C.muted(), size=16),
        bgcolor=C.surface(),
        border_radius=16,
        height=44,
        content_padding=12,
        border_color=C.input_border(),
        focused_border_color=C.accent(),
        on_change=on_search
    )

    result_count = ft.Text(f"{len(all_products)} spares in stock", size=11, color=C.muted())

    cats = ["All", "Body Parts", "Brake Parts", "Engine Parts", "Gear Parts", "Lubricants", "Service Parts", "Suspension Parts"]
    cat_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)

    def select_cat(selected_c):
        nonlocal current_cat
        current_cat = selected_c

        for btn in cat_row.controls:
            if isinstance(btn, ft.Container):
                is_selected = (btn.data == selected_c)
                btn.bgcolor = None if not is_selected else C.grad_primary()
                btn.shadow = C.soft_shadow() if is_selected else None
                btn.border = None if is_selected else ft.border.all(1, C.divider())
                if isinstance(btn.content, ft.Text):
                    btn.content.color = "white" if is_selected else C.body()

        filter_and_render()

    for c in cats:
        is_default = c == "All"
        cat_row.controls.append(
            ft.Container(
                data=c,
                content=ft.Text(c, color="white" if is_default else C.body(), size=11, weight=ft.FontWeight.BOLD),
                bgcolor=C.grad_primary() if is_default else C.surface(),
                border=ft.border.all(1, C.divider()) if not is_default else None,
                shadow=C.soft_shadow() if is_default else None,
                padding=ft.padding.symmetric(horizontal=13, vertical=8),
                border_radius=18,
                on_click=lambda e, cat=c: select_cat(cat)
            )
        )

    container.controls = [
        ft.Container(
            padding=ft.padding.only(left=15, right=15, top=4),
            content=ft.Row([
                ft.Column([
                    ft.Text("Browse Auto Spares", size=18, weight=ft.FontWeight.BOLD, color=C.text()),
                    result_count,
                ], spacing=1, tight=True),
                ft.Container(width=4),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=search_tf),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=cat_row),
        # Generous bottom padding to allow scrolling past the floating footer
        ft.Container(padding=ft.padding.only(left=15, right=15, bottom=120), content=grid_container)
    ]

    filter_and_render()
    return container