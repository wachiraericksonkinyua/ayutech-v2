import flet as ft
from app.ui.state import all_products, wishlist
from app.ui import colors as C

def build_browse_view(page: ft.Page, update_cart_callback, update_wishlist_callback, open_detail_callback):
    container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)
    
    current_cat = "All"
    current_query = ""

    grid_container = ft.Container()

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
                content=ft.Text("No matching auto parts found.", color="gray", size=13)
            )
        else:
            for p in prods:
                is_fav = p["id"] in wishlist
                img_url = p.get("image_url") or "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"
                grid.controls.append(
                    ft.Container(
                        bgcolor=C.surface(), border_radius=16, padding=10, border=ft.border.all(1, C.divider()),
                        on_click=lambda e, item=p: open_detail_callback(item),
                        content=ft.Column([
                            ft.Stack([
                                ft.Container(
                                    height=100, border_radius=12, bgcolor="white", alignment=ft.alignment.center, padding=5,
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
                                    style=ft.ButtonStyle(overlay_color={"hovered": "#DC2626"}),
                                    on_click=lambda e, item=p: update_cart_callback(item)
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    )
                )
            grid_container.content = grid
        page.update()

    def on_search(e):
        nonlocal current_query
        current_query = e.control.value.strip().lower() if e.control.value else ""
        filter_and_render()

    search_tf = ft.TextField(
        hint_text="Search auto parts (e.g. rack end, brake pads)...",
        hint_style=ft.TextStyle(color=C.muted(), size=12),
        bgcolor=C.surface_alt(), border_radius=15, height=42, content_padding=10,
        border_color="transparent", focused_border_color="#DC2626",
        on_change=on_search
    )

    cats = ["All", "Body Parts", "Brake Parts", "Engine Parts", "Gear Parts", "Lubricants", "Service Parts", "Suspension Parts"]
    cat_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)

    def select_cat(selected_c):
        nonlocal current_cat
        current_cat = selected_c
        
        for btn in cat_row.controls:
            if isinstance(btn, ft.Container):
                is_selected = (btn.data == selected_c)
                btn.bgcolor = "#121212" if is_selected else "#F3F4F6"
                if isinstance(btn.content, ft.Text):
                    btn.content.color = "white" if is_selected else "#121212"
        
        filter_and_render()

    for c in cats:
        cat_row.controls.append(
            ft.Container(
                data=c,
                content=ft.Text(c, color="white" if c == "All" else "#121212", size=11, weight=ft.FontWeight.BOLD),
                bgcolor=C.text() if c == "All" else "#F3F4F6",
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=15,
                on_click=lambda e, cat=c: select_cat(cat)
            )
        )

    container.controls = [
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=ft.Text("Browse Auto Spares", size=18, weight=ft.FontWeight.BOLD, color=C.text())),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=search_tf),
        ft.Container(padding=ft.padding.symmetric(horizontal=15), content=cat_row),
        # Generous bottom padding to allow scrolling past the floating footer
        ft.Container(padding=ft.padding.only(left=15, right=15, bottom=120), content=grid_container)
    ]

    filter_and_render()
    return container