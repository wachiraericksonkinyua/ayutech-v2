# app/ui/views/track_view.py
# Public order tracking by phone - no login required.

import datetime
import httpx
import flet as ft
from app.ui.state import API_BASE_URL
from app.ui import colors as C
from app.ui.notifications import notify

STATUS_COLORS = {
    "Pending PIN": "#F59E0B",
    "Processing": "#3B82F6",
    "Paid": "#16A34A",
    "Fulfilled": "#16A34A",
    "Cancelled": "#EF4444",
}


def _status_chip(status: str):
    color = STATUS_COLORS.get(status or "", "#6B7280")
    return ft.Container(
        bgcolor=color, border_radius=10,
        padding=ft.padding.symmetric(horizontal=9, vertical=3),
        content=ft.Text(status or "Unknown", size=11, color="white", weight=ft.FontWeight.BOLD),
    )


def build_track_page(page: ft.Page, back_callback):
    phone_field = ft.TextField(
        label="Phone number used at checkout",
        hint_text="e.g. 0712345678",
        border_color="red", focused_border_color=C.accent(),
        bgcolor=C.field(), text_size=13, height=45,
        keyboard_type=ft.KeyboardType.PHONE,
    )

    result_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    spinner = ft.ProgressRing(width=26, height=26, stroke_width=3, color=C.accent(), visible=False)

    def _fmt_date(iso_str):
        if not iso_str:
            return datetime.datetime.now().strftime("%d %b %Y, %H:%M")
        try:
            dt = datetime.datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            return dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            return str(iso_str)[:16]

    def _render_orders(orders):
        result_col.controls.clear()
        if not orders:
            result_col.controls.append(
                ft.Container(
                    padding=ft.padding.all(30), alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF, size=46, color=C.muted()),
                        ft.Text("No orders found for this number.", size=14, weight=ft.FontWeight.BOLD, color=C.soft()),
                        ft.Text("Double-check the phone or place a new order.", size=11, color=C.muted()),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            )
            page.update()
            return

        for o in orders:
            items = o.get("items") or []
            item_hint = f"{len(items)} item(s)" if len(items) > 3 else ", ".join(
                str(i.get("name", "Part"))[:22] for i in items[:3]
            )
            result_col.controls.append(
                ft.Container(
                    bgcolor=C.surface(), border_radius=14, padding=14,
                    border=ft.border.all(1, C.divider()),
                    content=ft.Column([
                        ft.Row([
                            ft.Column([
                                ft.Text(o.get("order_reference", "AYU-????"), size=15, weight=ft.FontWeight.BOLD, color=C.text()),
                                ft.Text(_fmt_date(o.get("created_at")), size=11, color=C.muted()),
                            ], spacing=2, expand=True),
                            _status_chip(o.get("status")),
                        ]),
                        item_hint and ft.Text(item_hint, size=12, color=C.body(), max_lines=1),
                        ft.Divider(height=14, color=C.divider()),
                        ft.Row([
                            ft.Text(f"KES {float(o.get('total') or 0):,.0f}", size=15, weight=ft.FontWeight.BOLD, color=C.accent()),
                            ft.Text(f"{o.get('payment_method') or ''}  •  {o.get('fulfillment') or ''}", size=11, color=C.muted()),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        o.get("receipt_number") and ft.Text(f"Receipt: {o['receipt_number']}", size=11, color=C.success()),
                    ], spacing=6, tight=True),
                )
            )
        result_col.controls.append(
            ft.Text("Tip: the status updates after M-Pesa confirms your payment.", size=11, color=C.muted())
        )
        page.update()

    def do_track(e):
        phone = "".join(ch for ch in (phone_field.value or "") if ch.isdigit())
        if len(phone) < 9:
            notify(page, "Enter a valid phone number (e.g. 0712345678).", "#DC2626", ft.icons.ERROR_OUTLINE, title="Invalid Phone")
            return
        result_col.controls.clear()
        spinner.visible = True
        page.update()
        try:
            res = httpx.get(f"{API_BASE_URL}/orders/track/{phone}", timeout=10)
            if res.status_code == 200:
                orders = res.json().get("orders", [])
            else:
                orders = []
                try:
                    rd = res.json().get("detail", f"Failed ({res.status_code}).")
                except Exception:
                    rd = f"Failed ({res.status_code})."
                notify(page, rd, "#DC2626", ft.icons.ERROR_OUTLINE, title="Tracking Failed")
            spinner.visible = False
            _render_orders(orders)
        except Exception as err:
            spinner.visible = False
            notify(page, f"Connection error: {err}", "#DC2626", ft.icons.ERROR_OUTLINE, title="Tracking Failed")
            page.update()

    track_btn = ft.ElevatedButton(
        "Track My Order", bgcolor=C.accent(), color="white", height=45,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=do_track,
    )

    return ft.Container(
        bgcolor=C.bg(), padding=0, expand=True,
        content=ft.Column([
            ft.Container(
                padding=ft.padding.only(left=10, right=15, top=8, bottom=8),
                content=ft.Row([
                    ft.IconButton(ft.icons.ARROW_BACK, icon_color=C.text(), on_click=lambda e: back_callback()),
                    ft.Text("Track My Order", size=18, weight=ft.FontWeight.BOLD, color=C.text()),
                ], spacing=4),
            ),
            ft.Container(
                padding=ft.padding.only(left=15, right=15),
                content=ft.Column([
                    ft.Text("Enter the phone number you used at checkout to see your latest orders and payment status.", size=12, color=C.body()),
                    phone_field,
                    ft.Row([track_btn, spinner], spacing=10),
                    ft.Container(height=8),
                    result_col,
                ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
            ),
        ], spacing=0),
    )