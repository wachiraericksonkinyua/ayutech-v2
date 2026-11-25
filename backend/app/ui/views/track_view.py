# app/ui/views/track_view.py
# Public order tracking by phone - no login required.

import datetime
import httpx
import flet as ft
from app.ui.state import API_BASE_URL
from app.ui import colors as C
from app.ui.notifications import notify
from app.ui.api import user_facing_error

def _status_chip(status: str):
    normalized = (status or "").strip().lower().replace("_", " ")
    if normalized in {"paid", "fulfilled", "delivered", "completed"}:
        color = "#16A34A"
    elif normalized in {"pending", "pending pin", "processing"}:
        color = "#D97706"
    elif normalized in {"cancelled", "canceled", "payment failed", "failed", "error"}:
        color = "#EF4444"
    else:
        color = "#6B7280"
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
    reference_field = ft.TextField(
        label="Order reference",
        hint_text="e.g. AYU-000123",
        border_color="red", focused_border_color=C.accent(),
        bgcolor=C.field(), text_size=13, height=45,
    )

    result_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    spinner = ft.ProgressRing(width=26, height=26, stroke_width=3, color=C.accent(), visible=False)
    button_spinner = ft.ProgressRing(width=15, height=15, stroke_width=2, color="white", visible=False)
    button_label = ft.Text("Track My Order", color="white", size=12, weight=ft.FontWeight.BOLD)
    loading_skeleton = ft.Container(
        visible=False,
        padding=14,
        bgcolor=C.surface(),
        border=ft.border.all(1, C.divider()),
        border_radius=14,
        content=ft.Column([
            ft.Container(height=14, width=170, bgcolor=C.surface_alt(), border_radius=7),
            ft.Container(height=10, width=250, bgcolor=C.surface_alt(), border_radius=5),
            ft.Container(height=10, width=205, bgcolor=C.surface_alt(), border_radius=5),
        ], spacing=10),
    )

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
            # build column children ensuring only Control instances are included
            col_children = []
            col_children.append(
                ft.Row([
                    ft.Column([
                        ft.Text(o.get("order_reference", "AYU-????"), size=15, weight=ft.FontWeight.BOLD, color=C.text()),
                        ft.Text(_fmt_date(o.get("created_at")), size=11, color=C.muted()),
                    ], spacing=2, expand=True),
                    _status_chip(o.get("status")),
                ])
            )
            if item_hint:
                col_children.append(ft.Text(item_hint, size=12, color=C.body(), max_lines=1))
            col_children.extend([
                ft.Divider(height=14, color=C.divider()),
                ft.Row([
                    ft.Text(f"KES {float(o.get('total_amount') or o.get('total') or 0):,.0f}", size=15, weight=ft.FontWeight.BOLD, color=C.accent()),
                    ft.Text(f"{o.get('payment_method') or ''}  •  {o.get('fulfillment') or ''}", size=11, color=C.muted()),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ])
            if o.get("receipt_number"):
                col_children.append(ft.Text(f"Receipt: {o['receipt_number']}", size=11, color=C.success()))

            result_col.controls.append(
                ft.Container(
                    bgcolor=C.surface(), border_radius=14, padding=14,
                    border=ft.border.all(1, C.divider()),
                    content=ft.Column(col_children, spacing=6, tight=True),
                )
            )
        result_col.controls.append(
            ft.Text("Tip: the status updates after M-Pesa confirms your payment.", size=11, color=C.muted())
        )
        page.update()

    async def do_track(e):
        phone = "".join(ch for ch in (phone_field.value or "") if ch.isdigit())
        order_reference = (reference_field.value or "").strip()
        if len(phone) < 9:
            notify(page, "Enter a valid phone number (e.g. 0712345678).", C.accent(), ft.icons.ERROR_OUTLINE, title="Invalid Phone")
            return
        if not order_reference:
            notify(page, "Enter the order reference from your confirmation.", C.accent(), ft.icons.ERROR_OUTLINE, title="Missing Reference")
            return
        result_col.controls.clear()
        spinner.visible = True
        loading_skeleton.visible = True
        phone_field.disabled = True
        reference_field.disabled = True
        track_btn.disabled = True
        button_label.value = "Searching..."
        button_spinner.visible = True
        page.update()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(
                    f"{API_BASE_URL}/orders/track",
                    json={"order_reference": order_reference, "phone": phone},
                )
            if res.status_code == 200:
                order = res.json().get("order")
                orders = [order] if order else []
                _render_orders(orders)
            elif res.status_code == 404:
                message = (
                    "We couldn't find an order with that reference. "
                    "Please double-check your GWV-XXXXXXX code and try again."
                )
                result_col.controls.append(
                    ft.Container(
                        padding=14,
                        bgcolor="#FEF2F2",
                        border=ft.border.all(1, "#FECACA"),
                        border_radius=12,
                        content=ft.Text(message, size=12, color="#B91C1C"),
                    )
                )
                page.update()
            else:
                message = user_facing_error(
                    res,
                    "We couldn't check your order right now. Please try again shortly.",
                )
                notify(page, message, C.danger(), ft.icons.ERROR_OUTLINE, title="Tracking Failed")
        except httpx.HTTPError:
            notify(
                page,
                "We couldn't connect to order tracking. Check your connection and try again.",
                C.danger(),
                ft.icons.ERROR_OUTLINE,
                title="Tracking Failed",
            )
        except (ValueError, TypeError, AttributeError):
            notify(
                page,
                "We couldn't read the tracking response. Please try again shortly.",
                C.danger(),
                ft.icons.ERROR_OUTLINE,
                title="Tracking Failed",
            )
        finally:
            spinner.visible = False
            loading_skeleton.visible = False
            phone_field.disabled = False
            reference_field.disabled = False
            track_btn.disabled = False
            button_label.value = "Track My Order"
            button_spinner.visible = False
            page.update()

    track_btn = ft.ElevatedButton(
        content=ft.Row([button_spinner, button_label], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        bgcolor=C.accent(), color="white", height=45,
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
                    ft.Text("Enter the order reference and phone number used at checkout to check payment status.", size=12, color=C.body()),
                    reference_field,
                    phone_field,
                    ft.Row([track_btn, spinner], spacing=10),
                    ft.Container(height=8),
                    loading_skeleton,
                    result_col,
                ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
            ),
        ], spacing=0),
    )