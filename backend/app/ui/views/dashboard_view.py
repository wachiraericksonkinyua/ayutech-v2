# app/ui/views/dashboard_view.py

import flet as ft
import httpx
import threading
import time
from app.ui.state import API_BASE_URL
from app.ui import colors as C

def build_dashboard_view(page: ft.Page):
    admin_orders = []
    active_filter = "All"
    search_query = ""

    # UI Containers
    metrics_row = ft.Row(spacing=10)
    orders_table_container = ft.Column(spacing=10)
    filter_chips_row = ft.Row(spacing=8)

    def get_badge_style(status: str):
        if status == "Paid":
            return C.success(), C.success_soft(), ft.icons.CHECK_CIRCLE_OUTLINE
        elif status == "Fulfilled":
            return C.info(), C.info_soft(), ft.icons.LOCAL_SHIPPING_OUTLINED
        elif status in ["Cancelled", "Payment Failed", "Failed"]:
            return C.muted(), C.surface_alt(), ft.icons.CANCEL_OUTLINED
        return C.warn(), C.warn_soft(), ft.icons.HOURGLASS_EMPTY

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
                    bgcolor=C.info()
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

        def metric_card(title: str, val: str, icon, accent: str, soft: str):
            return ft.Container(
                expand=True,
                padding=12,
                bgcolor=C.surface(),
                border_radius=14,
                border=ft.border.all(1, C.divider()),
                shadow=C.soft_shadow(),
                content=ft.Column([
                    ft.Container(
                        width=32, height=32, bgcolor=soft, border_radius=10,
                        alignment=ft.alignment.center,
                        content=ft.Icon(icon, color=accent, size=17),
                    ),
                    ft.Text(val, size=15, weight=ft.FontWeight.BOLD, color=C.text(), font_family="Roboto"),
                    ft.Text(title, size=10, color=C.muted(), weight=ft.FontWeight.W_500),
                ], spacing=5)
            )

        metrics_row.controls.extend([
            metric_card("Revenue", f"KES {total_revenue:,.0f}", ft.icons.ACCOUNT_BALANCE_WALLET_OUTLINED, C.accent(), C.accent_soft()),
            metric_card("Paid", str(paid_count), ft.icons.CHECK_CIRCLE_OUTLINE, C.success(), C.success_soft()),
            metric_card("Fulfilled", str(fulfilled_count), ft.icons.LOCAL_SHIPPING_OUTLINED, C.info(), C.info_soft()),
            metric_card("Pending", str(pending_count), ft.icons.HOURGLASS_EMPTY, C.warn(), C.warn_soft()),
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
                    padding=36,
                    bgcolor=C.surface(),
                    border_radius=16,
                    border=ft.border.all(1, C.divider()),
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF, size=42, color=C.muted()),
                        ft.Text("No orders match the current filter", size=13, color=C.soft())
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                )
            )
            return

        for ord_data in filtered:
            status = ord_data.get("status", "Pending PIN")
            accent, soft, badge_icon = get_badge_style(status)
            total_val = float(ord_data.get("total_amount") or ord_data.get("total") or 0)
            receipt = ord_data.get("receipt_number") or "None"
            phone = ord_data.get("customer_phone") or ord_data.get("phone") or "N/A"
            db_id = ord_data.get("id")

            # Action button
            action_btn = ft.Container()
            if status == "Paid":
                action_btn = ft.ElevatedButton(
                    "Mark Fulfilled",
                    bgcolor=C.info(),
                    color="white",
                    height=32,
                    icon=ft.icons.DONE_ALL,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=12),
                    ),
                    on_click=lambda e, oid=db_id: update_order_fulfillment(oid, "Fulfilled")
                )

            orders_table_container.controls.append(
                ft.Container(
                    bgcolor=C.surface(),
                    border_radius=16,
                    padding=14,
                    border=ft.border.all(1, C.divider()),
                    shadow=C.soft_shadow(),
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                width=30, height=30, bgcolor=soft, border_radius=9,
                                alignment=ft.alignment.center,
                                content=ft.Icon(badge_icon, size=16, color=accent),
                            ),
                            ft.Text(f"#{ord_data.get('order_reference', 'N/A')}", weight=ft.FontWeight.BOLD, size=13, color=C.text()),
                            ft.Container(expand=True),
                            ft.Container(
                                bgcolor=accent,
                                padding=ft.padding.symmetric(horizontal=9, vertical=3),
                                border_radius=8,
                                content=ft.Text(status, size=10, color="white", weight=ft.FontWeight.BOLD)
                            )
                        ], spacing=8),

                        ft.Divider(color=C.divider(), height=14),

                        ft.Row([
                            ft.Column([
                                ft.Row([
                                    ft.Icon(ft.icons.PHONE_OUTLINED, size=12, color=C.muted()),
                                    ft.Text(f"{phone}", size=11, color=C.body()),
                                ], spacing=4),
                                ft.Row([
                                    ft.Icon(ft.icons.RECEIPT_OUTLINED, size=12, color=C.muted()),
                                    ft.Text(f"{receipt}", size=11, color=C.body(), weight=ft.FontWeight.BOLD),
                                ], spacing=4),
                                ft.Row([
                                    ft.Icon(ft.icons.PLACE_OUTLINED, size=12, color=C.muted()),
                                    ft.Text(f"{ord_data.get('fulfillment', 'Shop Pickup')}", size=11, color=C.body()),
                                ], spacing=4),
                            ], spacing=5),
                            ft.Column([
                                ft.Text(f"KES {total_val:,.0f}", size=15, weight=ft.FontWeight.BOLD, color=C.accent()),
                                action_btn
                            ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=6)
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
        render_chips()
        render_dashboard()
        page.update()

    def render_chips():
        filter_chips_row.controls.clear()
        for name in ["All", "Paid", "Fulfilled", "Pending"]:
            selected = active_filter == name or (name == "Pending" and active_filter == "Pending PIN")
            filter_chips_row.controls.append(
                ft.Container(
                    data=name,
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    border_radius=16,
                    bgcolor=C.grad_primary() if selected else C.surface_alt(),
                    shadow=C.soft_shadow() if selected else None,
                    on_click=lambda e, nm=name: set_filter(nm),
                    content=ft.Text(
                        name,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color="white" if selected else C.body(),
                    ),
                )
            )

    # Search Bar
    search_bar = ft.TextField(
        prefix_icon=ft.icons.SEARCH,
        hint_text="Search by Order #, M-Pesa Receipt, or Phone...",
        hint_style=ft.TextStyle(color=C.muted(), size=12),
        border_color=C.input_border(),
        focused_border_color=C.accent(),
        bgcolor=C.field(),
        height=44,
        text_size=12,
        content_padding=12,
        on_change=on_search_change
    )

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
    render_chips()
    render_dashboard()
    threading.Thread(target=start_admin_polling, daemon=True).start()

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=0, bottom=120),
        bgcolor=C.bg(),
        expand=True,
        content=ft.Column([
            ft.Container(
                padding=ft.padding.only(left=18, right=12, top=14, bottom=16),
                bgcolor=C.grad_deep(),
                border_radius=ft.border_radius.only(bottom_left=22, bottom_right=22),
                content=ft.Row([
                    ft.Row([
                        ft.Container(
                            width=42, height=42, bgcolor=C.accent(), border_radius=13,
                            alignment=ft.alignment.center,
                            content=ft.Icon(ft.icons.SPEED, color="white", size=22),
                        ),
                        ft.Column([
                            ft.Text("Admin Dashboard", size=17, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Text("Live order centre · auto-sync", size=11, color="#B6AEA4"),
                        ], spacing=1),
                    ], spacing=12),
                    ft.IconButton(
                        icon=ft.icons.REFRESH,
                        icon_color="white",
                        bgcolor="#22FFFFFF",
                        tooltip="Sync Now",
                        on_click=lambda e: (fetch_orders_from_server(), render_dashboard(), page.update())
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ),
            ft.Container(height=2),
            metrics_row,
            search_bar,
            filter_chips_row,
            orders_table_container
        ], scroll=ft.ScrollMode.AUTO, spacing=14)
    )