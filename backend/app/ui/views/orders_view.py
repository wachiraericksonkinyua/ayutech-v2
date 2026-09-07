# app/ui/views/orders_view.py

import flet as ft
import httpx
import threading
import time
from app.ui.state import my_orders, API_BASE_URL

def build_orders_view(page: ft.Page):
    orders_list_container = ft.Column(spacing=12)

    def get_badge_color(status: str) -> str:
        if status == "Paid":
            return "#25D366"       # Green
        elif status == "Fulfilled":
            return "#2563EB"      # Blue
        elif status in ["Cancelled", "Payment Failed", "Failed"]:
            return "#6B7280"      # Gray
        return "#DC2626"          # Red for Pending / Pending PIN

    def show_receipt_dialog(ord_data: dict):
        """Displays a structured receipt modal when an order is tapped."""
        status = ord_data.get("status", "Pending PIN")
        badge_color = get_badge_color(status)
        receipt_no = ord_data.get("receipt_number", "Pending Confirmation")

        items_breakdown = ft.Column(spacing=8)
        for item in ord_data.get("items", []):
            item_total = float(item.get("price", 0)) * int(item.get("qty", 1))
            items_breakdown.controls.append(
                ft.Row([
                    ft.Column([
                        ft.Text(item.get("name", "Product"), size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                        ft.Text(f"Qty: {item.get('qty', 1)} × KES {float(item.get('price', 0)):,.0f}", size=11, color="#6B7280")
                    ], expand=True),
                    ft.Text(f"KES {item_total:,.0f}", size=13, weight=ft.FontWeight.BOLD, color="#121212")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        modal_content = ft.Container(
            width=360,
            padding=15,
            content=ft.Column([
                # Header with Status
                ft.Row([
                    ft.Column([
                        ft.Text(f"Order #{ord_data.get('order_id')}", size=16, weight=ft.FontWeight.BOLD, color="#121212"),
                        ft.Text(ord_data.get("date", ""), size=11, color="#9CA3AF")
                    ]),
                    ft.Container(
                        bgcolor=badge_color,
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        border_radius=8,
                        content=ft.Text(status, size=11, color="white", weight=ft.FontWeight.BOLD)
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Divider(color="#E5E7EB"),

                # Transaction & Delivery Details
                ft.Row([
                    ft.Text("M-Pesa Receipt:", size=12, color="#6B7280"),
                    ft.Text(receipt_no, size=12, weight=ft.FontWeight.BOLD, color="#121212")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text("Fulfillment:", size=12, color="#6B7280"),
                    ft.Text(ord_data.get("fulfillment", "Shop Pickup"), size=12, weight=ft.FontWeight.BOLD, color="#121212")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text("Payment Mode:", size=12, color="#6B7280"),
                    ft.Text(ord_data.get("payment_method", "M-Pesa"), size=12, weight=ft.FontWeight.BOLD, color="#121212")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Divider(color="#E5E7EB"),

                # Item list
                ft.Text("Purchased Items", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                items_breakdown,

                ft.Divider(color="#E5E7EB"),

                # Total Amount
                ft.Row([
                    ft.Text("Grand Total Paid", size=14, weight=ft.FontWeight.BOLD, color="#121212"),
                    ft.Text(f"KES {float(ord_data.get('total', 0)):,.0f}", size=16, weight=ft.FontWeight.BOLD, color="#DC2626")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=10, tight=True)
        )

        receipt_dialog = ft.AlertDialog(
            title=ft.Text("Order Receipt", weight=ft.FontWeight.BOLD, size=16),
            content=modal_content,
            actions=[
                ft.TextButton(
                    "Close",
                    style=ft.ButtonStyle(color="#DC2626"),
                    on_click=lambda e: close_dialog(receipt_dialog)
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=15)
        )

        page.dialog = receipt_dialog
        receipt_dialog.open = True
        page.update()

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    def sync_orders_status() -> bool:
        has_changes = False
        for ord in my_orders:
            if ord.get("status") in ["Pending", "Pending PIN"]:
                order_id = ord.get("order_id")
                try:
                    res = httpx.get(f"{API_BASE_URL}/orders/status/{order_id}", timeout=4)
                    if res.status_code == 200:
                        server_status = res.json().get("status")
                        if server_status and server_status != ord.get("status"):
                            ord["status"] = server_status
                            has_changes = True
                except Exception as err:
                    print(f"Error syncing order {order_id}: {err}")
        return has_changes

    def render_orders():
        orders_list_container.controls.clear()

        if not my_orders:
            orders_list_container.controls.append(
                ft.Container(
                    bgcolor="#F9FAFB", border_radius=15, padding=30,
                    border=ft.border.all(1, "#E5E7EB"),
                    content=ft.Column([
                        ft.Icon(ft.icons.RECEIPT_LONG_OUTLINED, size=50, color="#DC2626"),
                        ft.Text("No active orders found", size=15, weight=ft.FontWeight.BOLD, color="#121212"),
                        ft.Text("Your completed M-Pesa purchases and pickup orders will appear here automatically.", size=12, color="#6B7280", text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
                )
            )
            return

        for ord in my_orders:
            items_detail = ft.Column(spacing=4)
            for itm in ord.get("items", []):
                items_detail.controls.append(
                    ft.Row([
                        ft.Text(f"• {itm['name']} (x{itm['qty']})", size=11, color="#4B5563"),
                        ft.Text(f"KES {itm['price']*itm['qty']:,.0f}", size=11, color="#121212", weight=ft.FontWeight.BOLD)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )

            status = ord.get("status", "Pending PIN")
            badge_color = get_badge_color(status)

            order_card = ft.Container(
                bgcolor="#F9FAFB", border_radius=15, padding=15, border=ft.border.all(1, "#E5E7EB"),
                on_click=lambda e, current_order=ord: show_receipt_dialog(current_order),
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.icons.RECEIPT_OUTLINED, size=16, color="#DC2626"),
                            ft.Text(f"Order #{ord['order_id']}", size=13, weight=ft.FontWeight.BOLD, color="#121212"),
                        ], spacing=6),
                        ft.Container(
                            bgcolor=badge_color,
                            padding=ft.padding.symmetric(horizontal=8, vertical=3), border_radius=8,
                            content=ft.Text(status, size=10, color="white", weight=ft.FontWeight.BOLD)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(ord["date"], size=11, color="#9CA3AF"),
                    ft.Divider(color="#E5E7EB"),
                    items_detail,
                    ft.Divider(color="#E5E7EB"),
                    ft.Row([
                        ft.Text(f"{ord['fulfillment']} • {ord['payment_method']}", size=11, color="#6B7280"),
                        ft.Text(f"KES {ord['total']:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="#DC2626")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text("Tap to view full receipt", size=10, color="#9CA3AF", italic=True)
                ], spacing=6)
            )
            orders_list_container.controls.append(order_card)

    def on_refresh_click(e):
        sync_orders_status()
        render_orders()
        page.update()

    def start_polling_loop():
        while True:
            pending_exists = any(o.get("status") in ["Pending", "Pending PIN"] for o in my_orders)
            if not pending_exists:
                break
            changed = sync_orders_status()
            if changed:
                render_orders()
                page.update()
            time.sleep(3)

    sync_orders_status()
    render_orders()
    threading.Thread(target=start_polling_loop, daemon=True).start()

    header_row = ft.Row([
        ft.Text("My Orders", size=22, weight=ft.FontWeight.BOLD, color="#121212"),
        ft.IconButton(
            icon=ft.icons.REFRESH,
            icon_color="#DC2626",
            tooltip="Refresh Status",
            on_click=on_refresh_click
        )
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        bgcolor="#FFFFFF",
        expand=True,
        content=ft.Column([
            header_row,
            orders_list_container
        ], scroll=ft.ScrollMode.AUTO, spacing=15)
    )