# app/ui/views/dashboard_view.py

import flet as ft
import httpx
import threading
import time
from app.ui.state import API_BASE_URL

def build_dashboard_view(page: ft.Page):
    admin_orders = []
    active_filter = "All"
    search_query = ""

    # UI Containers
    metrics_row = ft.Row(spacing=10)
    orders_table_container = ft.Column(spacing=10)

    def get_badge_styling(status: str):
        if status == "Paid":
            return "#25D366", "white"
        elif status == "Fulfilled":
            return "#2563EB", "white"
        elif status in ["Cancelled", "Payment Failed", "Failed"]:
            return "#6B7280", "white"
        return "#DC2626", "white"

    def fetch_orders_from_server() -> bool:
        """Fetches latest orders from the backend API."""
        nonlocal admin_orders
        try:
            res = httpx.get(f"{API_BASE_URL}/admin/orders", timeout=5)
            if res.status_code == 200:
                data = res.json().get("orders", [])
                if data != admin_orders:
                    admin_orders = data
                    return True
        except Exception as e:
            print(f"Admin orders fetch error: {e}")
        return False

    def update_order_fulfillment(order_db_id: str, new_status: str):
        """Dispatches an update to mark order as Fulfilled."""
        try:
            res = httpx.patch(
                f"{API_BASE_URL}/admin/orders/{order_db_id}/status",
                json={"status": new_status},
                timeout=5
            )
            if res.status_code == 200:
                fetch_orders_from_server()
                render_dashboard()
                page.snack_bar = ft.SnackBar(
                    ft.Text(f"✅ Order marked as {new_status}!"),
                    bgcolor="#2563EB"
                )
                page.snack_bar.open = True
                page.update()
        except Exception as e:
            print(f"Error marking status: {e}")

    def render_metrics():
        metrics_row.controls.clear()

        total_revenue = sum(
            float(o.get("total_amount") or o.get("total") or 0)
            for o in admin_orders
            if o.get("status") in ["Paid", "Fulfilled"]
        )
        paid_count = sum(1 for o in admin_orders if o.get("status") == "Paid")
        fulfilled_count = sum(1 for o in admin_orders if o.get("status") == "Fulfilled")
        pending_count = sum(1 for o in admin_orders if o.get("status") in ["Pending", "Pending PIN"])

        def metric_card(title: str, val: str, icon, color: str):
            return ft.Container(
                expand=True,
                padding=14,
                bgcolor="#F9FAFB",
                border_radius=12,
                border=ft.border.all(1, "#E5E7EB"),
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, color=color, size=18),
                        ft.Text(title, size=11, color="#6B7280", weight=ft.FontWeight.W_500)
                    ], spacing=6),
                    ft.Text(val, size=16, weight=ft.FontWeight.BOLD, color="#121212")
                ], spacing=4)
            )

        metrics_row.controls.extend([
            metric_card("Revenue", f"KES {total_revenue:,.0f}", ft.icons.ACCOUNT_BALANCE_WALLET, "#25D366"),
            metric_card("Paid", str(paid_count), ft.icons.CHECK_CIRCLE_OUTLINE, "#25D366"),
            metric_card("Fulfilled", str(fulfilled_count), ft.icons.LOCAL_SHIPPING_OUTLINED, "#2563EB"),
            metric_card("Pending", str(pending_count), ft.icons.HOURGLASS_EMPTY, "#DC2626")
        ])

    def render_orders_list():
        orders_table_container.controls.clear()

        # Apply search and status filtering
        filtered = []
        for o in admin_orders:
            ref = str(o.get("order_reference", "")).lower()
            phone = str(o.get("customer_phone") or o.get("phone") or "").lower()
            receipt = str(o.get("receipt_number", "")).lower()
            status = str(o.get("status", ""))

            matches_search = (
                search_query in ref or search_query in phone or search_query in receipt
            )
            matches_filter = (
                active_filter == "All" or status.lower() == active_filter.lower()
            )

            if matches_search and matches_filter:
                filtered.append(o)

        if not filtered:
            orders_table_container.controls.append(
                ft.Container(
                    padding=30,
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF, size=40, color="#9CA3AF"),
                        ft.Text("No orders match the current filter", size=13, color="#6B7280")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )
            return

        for ord_data in filtered:
            status = ord_data.get("status", "Pending PIN")
            bg_color, text_color = get_badge_styling(status)
            total_val = float(ord_data.get("total_amount") or ord_data.get("total") or 0)
            receipt = ord_data.get("receipt_number") or "None"
            phone = ord_data.get("customer_phone") or ord_data.get("phone") or "N/A"
            db_id = ord_data.get("id")

            # Action button
            action_btn = ft.Container()
            if status == "Paid":
                action_btn = ft.ElevatedButton(
                    "Mark Fulfilled",
                    bgcolor="#2563EB",
                    color="white",
                    height=32,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.padding.symmetric(horizontal=10)
                    ),
                    on_click=lambda e, oid=db_id: update_order_fulfillment(oid, "Fulfilled")
                )

            orders_table_container.controls.append(
                ft.Container(
                    bgcolor="#F9FAFB",
                    border_radius=12,
                    padding=14,
                    border=ft.border.all(1, "#E5E7EB"),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Icon(ft.icons.RECEIPT, size=16, color="#DC2626"),
                                ft.Text(f"#{ord_data.get('order_reference', 'N/A')}", weight=ft.FontWeight.BOLD, size=13, color="#121212"),
                            ], spacing=6),
                            ft.Container(
                                bgcolor=bg_color,
                                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6,
                                content=ft.Text(status, size=10, color=text_color, weight=ft.FontWeight.BOLD)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                        ft.Divider(color="#E5E7EB"),

                        ft.Row([
                            ft.Column([
                                ft.Text(f"Phone: {phone}", size=11, color="#4B5563"),
                                ft.Text(f"Receipt: {receipt}", size=11, color="#4B5563", weight=ft.FontWeight.BOLD),
                                ft.Text(f"Fulfillment: {ord_data.get('fulfillment', 'Shop Pickup')}", size=11, color="#6B7280"),
                            ], spacing=2),
                            ft.Column([
                                ft.Text(f"KES {total_val:,.0f}", size=14, weight=ft.FontWeight.BOLD, color="#DC2626"),
                                action_btn
                            ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=4)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=6)
                )
            )

    def render_dashboard():
        render_metrics()
        render_orders_list()

    def on_search_change(e):
        nonlocal search_query
        search_query = (e.control.value or "").strip().lower()
        render_orders_list()
        page.update()

    def set_filter(f_name):
        nonlocal active_filter
        active_filter = f_name
        render_dashboard()
        page.update()

    # Search Bar
    search_bar = ft.TextField(
        prefix_icon=ft.icons.SEARCH,
        hint_text="Search by Order #, M-Pesa Receipt, or Phone...",
        border_color="#E5E7EB",
        focused_border_color="#DC2626",
        bgcolor="#F9FAFB",
        height=44,
        text_size=12,
        on_change=on_search_change
    )

    # Filter Chips
    filter_chips = ft.Row([
        ft.OutlinedButton("All", style=ft.ButtonStyle(color="#121212"), on_click=lambda e: set_filter("All")),
        ft.OutlinedButton("Paid", style=ft.ButtonStyle(color="#25D366"), on_click=lambda e: set_filter("Paid")),
        ft.OutlinedButton("Fulfilled", style=ft.ButtonStyle(color="#2563EB"), on_click=lambda e: set_filter("Fulfilled")),
        ft.OutlinedButton("Pending", style=ft.ButtonStyle(color="#DC2626"), on_click=lambda e: set_filter("Pending PIN")),
    ], scroll=ft.ScrollMode.AUTO, spacing=8)

    # Background Live Sync Loop
    def start_admin_polling():
        while True:
            changed = fetch_orders_from_server()
            if changed:
                render_dashboard()
                page.update()
            time.sleep(5)

    # Initial Load & Start Polling
    fetch_orders_from_server()
    render_dashboard()
    threading.Thread(target=start_admin_polling, daemon=True).start()

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        bgcolor="#FFFFFF",
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Text("Admin Live Orders", size=22, weight=ft.FontWeight.BOLD, color="#121212"),
                ft.IconButton(
                    icon=ft.icons.REFRESH,
                    icon_color="#DC2626",
                    tooltip="Sync Now",
                    on_click=lambda e: (fetch_orders_from_server(), render_dashboard(), page.update())
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            metrics_row,
            search_bar,
            filter_chips,
            orders_table_container
        ], scroll=ft.ScrollMode.AUTO, spacing=14)
    )