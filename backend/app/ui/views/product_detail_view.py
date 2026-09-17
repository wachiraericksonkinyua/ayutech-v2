import httpx
import threading
import flet as ft
from app.ui.state import API_BASE_URL, current_user_id, user_info, wishlist
from app.ui.notifications import notify
from app.ui import colors as C


def _fallback_img():
    return "https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png"


def build_product_detail_view(page: ft.Page, product: dict, back_callback, add_to_cart_callback, ask_fitment_callback=None):
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
        fav_btn.icon_color = C.accent() if is_fav else C.text()
        page.update()

    fav_btn = ft.IconButton(
        icon=ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER,
        icon_color=C.accent() if is_fav else C.text(),
        on_click=toggle_fav
    )

    img_url = product.get("image_url") or _fallback_img()
    qty_val = ft.Text("1", size=14, weight=ft.FontWeight.BOLD, color=C.text())

    def update_qty(delta):
        current = int(qty_val.value or "1")
        new_qty = max(1, current + delta)
        qty_val.value = str(new_qty)
        page.update()

    def call_store(e):
        page.launch_url("tel:+254712345678")

    def whatsapp_store(e):
        msg = f"Hello Ayutech Motors, I am inquiring about {product['name']} (KES {product['price']:,.0f})"
        page.launch_url(f"https://wa.me/254712345678?text={msg}")

    header_bar = ft.Container(
        padding=15,
        content=ft.Row([
            ft.IconButton(ft.icons.ARROW_BACK, icon_color=C.text(), on_click=lambda e: back_callback()),
            ft.Text("Product Details", size=16, weight=ft.FontWeight.BOLD, color=C.text()),
            fav_btn
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    image_preview = ft.Container(
        height=220, border_radius=20, bgcolor=C.surface_alt(), alignment=ft.alignment.center,
        padding=15, content=ft.Image(src=img_url, fit=ft.ImageFit.CONTAIN,
                                     error_content=ft.Icon(ft.icons.CAR_REPAIR, size=48, color=C.muted()))
    )

    action_buttons = ft.Row([
        ft.Container(
            expand=True, bgcolor=C.surface_alt(), border_radius=12, padding=10,
            on_click=call_store,
            content=ft.Row([ft.Icon(ft.icons.PHONE, size=16, color=C.accent()), ft.Text("Call Shop", size=12, weight=ft.FontWeight.BOLD, color=C.text())], alignment=ft.MainAxisAlignment.CENTER)
        ),
        ft.Container(
            expand=True, bgcolor=C.surface_alt(), border_radius=12, padding=10,
            on_click=whatsapp_store,
            content=ft.Row([ft.Icon(ft.icons.CHAT, size=16, color="#25D366"), ft.Text("WhatsApp", size=12, weight=ft.FontWeight.BOLD, color=C.text())], alignment=ft.MainAxisAlignment.CENTER)
        ),
        ft.Container(
            expand=True, bgcolor=C.surface_alt(), border_radius=12, padding=10,
            on_click=lambda e: ask_fitment_callback(product) if ask_fitment_callback else None,
            content=ft.Row([ft.Icon(ft.icons.AUTO_AWESOME, size=16, color="#6366F1"), ft.Text("AI Fitment", size=12, weight=ft.FontWeight.BOLD, color=C.text())], alignment=ft.MainAxisAlignment.CENTER)
        )
    ], spacing=10)

    prod_description = product.get("description") or (
        f"Genuine {product.get('category', 'automotive')} replacement part distributed by Ayutech Motors Limited. "
        "Engineered for high durability and exact OEM fitment on Kirinyaga Road standards."
    )

    # ---------- REVIEWS ----------
    reviews_col = ft.Column(spacing=8)
    rating_summary = ft.Text("Loading reviews...", size=12, color=C.muted())

    def _stars(rating: int, active_color=C.accent()):
        return ft.Row([
            ft.Icon(ft.icons.STAR if i <= int(rating) else ft.icons.STAR_OUTLINE,
                    color=active_color, size=16)
            for i in range(1, 6)
        ], spacing=1)

    def load_reviews():
        def _go():
            try:
                res = httpx.get(f"{API_BASE_URL}/reviews/product/{product['id']}", timeout=8)
                if res.status_code == 200:
                    _render(res.json())
            except Exception:
                pass

        def _render(data):
            avg = data.get("average", 0)
            count = data.get("count", 0)
            reviews = data.get("reviews", [])
            rating_summary.value = f"{avg:g} average • {count} review(s)" if count else "No reviews yet - be the first!"
            rating_summary.update()
            reviews_col.controls.clear()
            for r in reviews[:5]:
                reviews_col.controls.append(
                    ft.Container(
                        bgcolor=C.surface(), border_radius=10, padding=10,
                        border=ft.border.all(1, C.divider()),
                        content=ft.Column([
                            ft.Row([
                                ft.Container(
                                    width=30, height=30, bgcolor=C.accent_soft(), border_radius=15,
                                    alignment=ft.alignment.center,
                                    content=ft.Text(str(r.get("customer_name", "G"))[:1].upper(), size=12, weight=ft.FontWeight.BOLD, color=C.accent()),
                                ),
                                ft.Column([
                                    ft.Text(str(r.get("customer_name", "Customer"))[:24], size=12, weight=ft.FontWeight.BOLD, color=C.text()),
                                    _stars(r.get("rating", 0)),
                                ], spacing=1),
                            ], spacing=8),
                            r.get("comment") and ft.Text(str(r["comment"])[:400], size=12, color=C.body()),
                        ], spacing=6, tight=True),
                    )
                )
            page.update()
        threading.Thread(target=_go, daemon=True).start()

    def open_review_dialog(e):
        star_buttons = [
            ft.IconButton(
                icon=ft.icons.STAR_OUTLINE,
                icon_color=C.accent(),
                icon_size=30,
                tooltip=f"{i + 1} out of 5 stars",
            )
            for i in range(5)
        ]
        picked = {"rating": 0}
        comment_field = ft.TextField(
            label="Your feedback", hint_text="How was the part / service?", multiline=True,
            min_lines=2, max_lines=4, text_size=12, border_color="#DC2626", bgcolor=C.field(),
        )

        def pick_star(idx):
            picked["rating"] = idx + 1
            for i, b in enumerate(star_buttons):
                b.icon = ft.icons.STAR if i <= idx else ft.icons.STAR_OUTLINE
                b.icon_color = C.accent()
            page.update()

        for i, b in enumerate(star_buttons):
            b.on_click = lambda ev, idx=i: pick_star(idx)

        close_btn = ft.TextButton("Cancel")

        def submit(ev):
            if picked["rating"] < 1:
                notify(page, "Tap a star to rate the part.", "#DC2626", ft.icons.ERROR_OUTLINE, title="Rating Missing")
                return
            customer_name = (user_info.get("name") or user_info.get("email") or "").split("@")[0] or "Customer"
            payload = {
                "product_id": str(product["id"]),
                "customer_id": current_user_id or None,
                "customer_name": (customer_name or "Customer").capitalize(),
                "rating": picked["rating"],
                "comment": (comment_field.value or "").strip(),
            }
            try:
                res = httpx.post(f"{API_BASE_URL}/reviews/", json=payload, timeout=12)
                if res.status_code in [200, 201]:
                    notify(page, "Review submitted. Thank you!", "#16A34A", ft.icons.STAR, title="Review Posted")
                    dlg.open = False
                    page.update()
                    load_reviews()
                else:
                    detail = "Could not submit review."
                    try:
                        detail = res.json().get("detail", detail)
                    except Exception:
                        pass
                    notify(page, detail, "#DC2626", ft.icons.ERROR_OUTLINE, title="Review Failed")
            except Exception as err:
                notify(page, f"Submit error: {err}", "#DC2626", ft.icons.ERROR_OUTLINE, title="Review Failed")

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=C.bg(),
            shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Text("Rate this Part", size=16, weight=ft.FontWeight.BOLD, color=C.text()),
            content=ft.Column([
                ft.Row(star_buttons, spacing=2),
                ft.Text("Only verified buyers can review.", size=11, color=C.muted()),
                comment_field,
            ], tight=True, spacing=10),
            actions=[close_btn, ft.ElevatedButton("Submit", bgcolor=C.accent(), color="white", on_click=submit)],
        )
        close_btn.on_click = lambda ev: (setattr(dlg, "open", False), page.update())
        page.dialog = dlg
        dlg.open = True
        page.update()

    details_content = ft.Column([
        ft.Container(
            bgcolor=C.accent_soft(), border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=4),
            content=ft.Text(product.get("category", "Auto Part"), size=11, color=C.accent(), weight=ft.FontWeight.BOLD)
        ),
        ft.Text(product["name"], size=18, weight=ft.FontWeight.BOLD, color=C.text()),
        action_buttons,
        ft.Text("Description & Fitment Notes", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
        ft.Text(prod_description, size=12, color=C.body()),
        ft.Divider(color=C.divider()),
        ft.Row([
            ft.Text("Quantity:", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
            ft.Row([
                ft.IconButton(ft.icons.REMOVE, icon_size=16, icon_color="white", bgcolor=C.text(), on_click=lambda e: update_qty(-1)),
                qty_val,
                ft.IconButton(ft.icons.ADD, icon_size=16, icon_color="white", bgcolor=C.accent(), on_click=lambda e: update_qty(1)),
            ], spacing=10)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(color=C.divider()),
        ft.Row([
            ft.Text("Ratings & Reviews", size=13, weight=ft.FontWeight.BOLD, color=C.text()),
            rating_summary,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        reviews_col,
        ft.OutlinedButton(
            "Write a Review", icon=ft.icons.STAR_OUTLINE,
            style=ft.ButtonStyle(color=C.accent()),
            on_click=open_review_dialog,
        ),
        ft.Container(height=10),
    ], spacing=12)

    load_reviews()

    return ft.Column([
        header_bar,
        ft.Container(
            expand=True,
            bgcolor=C.bg(),
            padding=ft.padding.symmetric(horizontal=15),
            content=ft.Column([image_preview, details_content], scroll=ft.ScrollMode.AUTO, expand=True)
        ),
        ft.Container(
            padding=15, bgcolor=C.surface(), border=ft.border.only(top=ft.BorderSide(1, C.divider())),
            content=ft.Row([
                ft.Column([
                    ft.Text("Total Price", size=11, color=C.muted()),
                    ft.Text(f"KES {product['price']:,.0f}", size=18, weight=ft.FontWeight.BOLD, color=C.accent())
                ]),
                ft.ElevatedButton(
                    "Add to Cart",
                    icon=ft.icons.SHOPPING_BAG,
                    bgcolor=C.text(), color=C.bg(), height=45, width=170,
                    style=ft.ButtonStyle(),
                    on_click=lambda e: add_to_cart_callback(product, int(qty_val.value or "1"))
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )
    ], expand=True)