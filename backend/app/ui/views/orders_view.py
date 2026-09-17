# app/ui/views/orders_view.py

import json
import threading
import time
import flet as ft
import httpx
from app.ui.state import API_BASE_URL, current_user_id, my_orders


def build_orders_view(page: ft.Page):
  orders_list_container = ft.Column(spacing=12)

  def get_badge_color(status: str) -> str:
    s = (status or '').lower()
    if 'paid' in s or 'processing' in s:
      return '#25D366'  # Green
    elif 'fulfilled' in s:
      return '#2563EB'  # Blue
    elif 'cancel' in s or 'fail' in s:
      return '#6B7280'  # Gray
    return '#DC2626'  # Red for Pending / Pending PIN

  def show_receipt_dialog(ord_data: dict):
    status = ord_data.get('status', 'Pending PIN')
    badge_color = get_badge_color(status)
    receipt_no = ord_data.get('receipt_number', 'Pending Confirmation')
    order_ref = ord_data.get('order_reference') or ord_data.get(
        'order_id', 'N/A'
    )
    order_date = ord_data.get('date') or ord_data.get('created_at', '')[:10]

    receipt_input = ft.TextField(
        label='M-Pesa Code (e.g. UIA9U5Y7NU)',
        text_size=12,
        height=40,
        border_color='#DC2626',
    )

    def submit_manual_receipt(e):
      code = (receipt_input.value or '').strip()
      if not code:
        return
      try:
        res = httpx.post(
            f'{API_BASE_URL}/orders/verify-receipt',
            json={'order_reference': order_ref, 'receipt_number': code},
            timeout=5,
        )
        data = res.json()
        if res.status_code == 200:
          page.snack_bar = ft.SnackBar(
              ft.Text('✅ Order successfully verified!'), bgcolor='#16A34A'
          )
          page.snack_bar.open = True
          close_dialog(receipt_dialog)
          sync_orders_status()
          render_orders()
        else:
          page.snack_bar = ft.SnackBar(
              ft.Text(data.get('detail', 'Invalid receipt code.')),
              bgcolor='#DC2626',
          )
          page.snack_bar.open = True
        page.update()
      except Exception as err:
        print(f'Manual code entry error: {err}')

    verify_action_row = (
        ft.Container(
            content=ft.Row([
                ft.Container(content=receipt_input, expand=True),
                ft.ElevatedButton(
                    'Verify',
                    bgcolor='#DC2626',
                    color='white',
                    height=40,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    on_click=submit_manual_receipt,
                ),
            ], spacing=8),
            margin=ft.margin.symmetric(vertical=4),
        )
        if status in ['Pending', 'Pending PIN']
        else ft.Container()
    )

    # Safe parsing of items in receipt dialog
    raw_items = ord_data.get('items', [])
    if isinstance(raw_items, str):
      try:
        raw_items = json.loads(raw_items)
      except Exception:
        raw_items = []
    if not isinstance(raw_items, list):
      raw_items = []

    items_breakdown = ft.Column(spacing=8)
    for item in raw_items:
      if not isinstance(item, dict):
        continue
      qty = int(item.get('qty') or item.get('quantity') or 1)
      price = float(item.get('price') or 0)
      item_total = price * qty
      items_breakdown.controls.append(
          ft.Row([
              ft.Column([
                  ft.Text(
                      item.get('name', 'Product'),
                      size=13,
                      weight=ft.FontWeight.BOLD,
                      color='#121212',
                  ),
                  ft.Text(
                      f'Qty: {qty} × KES {price:,.0f}', size=11, color='#6B7280'
                  ),
              ], expand=True),
              ft.Text(
                  f'KES {item_total:,.0f}',
                  size=13,
                  weight=ft.FontWeight.BOLD,
                  color='#121212',
              ),
          ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
      )

    modal_content = ft.Container(
        width=360,
        padding=15,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(
                        f'Order #{order_ref}',
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color='#121212',
                    ),
                    ft.Text(order_date, size=11, color='#9CA3AF'),
                ]),
                ft.Container(
                    bgcolor=badge_color,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=8,
                    content=ft.Text(
                        status, size=11, color='white', weight=ft.FontWeight.BOLD
                    ),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(color='#E5E7EB'),
            ft.Row([
                ft.Text('M-Pesa Receipt:', size=12, color='#6B7280'),
                ft.Text(
                    receipt_no,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color='#121212',
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([
                ft.Text('Fulfillment:', size=12, color='#6B7280'),
                ft.Text(
                    ord_data.get('fulfillment', 'Shop Pickup'),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color='#121212',
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([
                ft.Text('Payment Mode:', size=12, color='#6B7280'),
                ft.Text(
                    ord_data.get('payment_method', 'M-Pesa'),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color='#121212',
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(color='#E5E7EB'),
            verify_action_row,
            ft.Divider(color='#E5E7EB'),
            ft.Text(
                'Purchased Items',
                size=13,
                weight=ft.FontWeight.BOLD,
                color='#121212',
            ),
            items_breakdown,
            ft.Divider(color='#E5E7EB'),
            ft.Row([
                ft.Text(
                    'Grand Total Paid',
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color='#121212',
                ),
                ft.Text(
                    f"KES {float(ord_data.get('total') or ord_data.get('total_amount') or 0):,.0f}",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color='#DC2626',
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=10, tight=True),
    )

    receipt_dialog = ft.AlertDialog(
        title=ft.Text('Order Receipt', weight=ft.FontWeight.BOLD, size=16),
        content=modal_content,
        actions=[
            ft.TextButton(
                'Close',
                style=ft.ButtonStyle(color='#DC2626'),
                on_click=lambda e: close_dialog(receipt_dialog),
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=15),
    )

    page.dialog = receipt_dialog
    receipt_dialog.open = True
    page.update()

  def close_dialog(dlg):
    dlg.open = False
    page.update()

  def fetch_backend_orders() -> bool:
    """Fetches persistent user orders from the FastAPI backend database."""
    import app.ui.state as app_state

    identifier = app_state.current_user_id or app_state.user_info.get('email')
    if not identifier:
      return False
    try:
      res = httpx.get(f'{API_BASE_URL}/orders/user/{identifier}', timeout=5)
      if res.status_code == 200:
        backend_orders = res.json().get('orders', [])
        added_new = False

        for bo in backend_orders:
          bo_id = bo.get('order_reference') or bo.get('id')
          existing = next(
              (
                  o
                  for o in my_orders
                  if o.get('order_reference') == bo_id
                  or o.get('order_id') == bo_id
              ),
              None,
          )
          if existing:
            existing['status'] = bo.get('status', existing['status'])
            existing['receipt_number'] = bo.get(
                'receipt_number', existing.get('receipt_number')
            )
          else:
            raw_items = bo.get('items', [])
            if isinstance(raw_items, str):
              try:
                raw_items = json.loads(raw_items)
              except Exception:
                raw_items = []

            my_orders.append({
                'order_id': bo.get('order_reference', bo.get('id', 'N/A')[:6]),
                'order_reference': bo.get('order_reference'),
                'date': bo.get('created_at', '')[:10],
                'status': bo.get('status', 'Pending PIN'),
                'fulfillment': bo.get('fulfillment', 'Shop Pickup'),
                'payment_method': bo.get('payment_method', 'M-Pesa'),
                'total': bo.get('total') or bo.get('total_amount', 0),
                'items': raw_items,
                'receipt_number': bo.get('receipt_number', ''),
            })
            added_new = True
        return added_new
    except Exception as err:
      print(f'Error fetching backend orders: {err}')
    return False

  def manual_verify_payment(order_ref):
    try:
      res = httpx.get(f'{API_BASE_URL}/orders/status/{order_ref}', timeout=5)
      if res.status_code == 200:
        data = res.json()
        new_status = data.get('status')
        new_receipt = data.get('receipt_number')

        for ord in my_orders:
          if (
              ord.get('order_reference') == order_ref
              or ord.get('order_id') == order_ref
          ):
            ord['status'] = new_status
            if new_receipt:
              ord['receipt_number'] = new_receipt

        page.snack_bar = ft.SnackBar(
            ft.Text(f'Status checked: {new_status}'),
            bgcolor='#25D366'
            if new_status in ['Paid', 'Processing']
            else '#DC2626',
        )
        page.snack_bar.open = True
        render_orders()
        page.update()
      else:
        try:
          detail = res.json().get('detail', f'Status lookup failed ({res.status_code}).')
        except Exception:
          detail = f'Status lookup failed ({res.status_code}).'
        page.snack_bar = ft.SnackBar(
            ft.Text(f'⚠️ {detail}'),
            bgcolor='#DC2626',
        )
        page.snack_bar.open = True
        page.update()
    except Exception as err:
      print(f'Manual verification error: {err}')

  def sync_orders_status() -> bool:
        has_changes = fetch_backend_orders()
        for ord in my_orders:
            # Skip polling if order is already completed/cancelled or a simulated local reference
            status = ord.get("status", "")
            order_ref = ord.get("order_reference") or ord.get("order_id")
            if not order_ref or status in ["Paid", "Fulfilled", "Cancelled", "Payment Failed"]:
                continue
                
            if order_ref:
                try:
                    res = httpx.get(f"{API_BASE_URL}/orders/status/{order_ref}", timeout=4)
                    if res.status_code == 200:
                        server_status = res.json().get("status")
                        server_receipt = res.json().get("receipt_number")
                        if server_status and server_status != ord.get("status"):
                            ord["status"] = server_status
                            has_changes = True
                        if server_receipt and server_receipt != ord.get("receipt_number"):
                            ord["receipt_number"] = server_receipt
                            has_changes = True
                except Exception as err:
                    print(f"Error syncing order {order_ref}: {err}")
        return has_changes

  def render_orders():
    orders_list_container.controls.clear()

    if not my_orders:
      orders_list_container.controls.append(
          ft.Container(
              bgcolor='#F9FAFB',
              border_radius=15,
              padding=30,
              border=ft.border.all(1, '#E5E7EB'),
              content=ft.Column([
                  ft.Icon(
                      ft.icons.RECEIPT_LONG_OUTLINED, size=50, color='#DC2626'
                  ),
                  ft.Text(
                      'No active orders found',
                      size=15,
                      weight=ft.FontWeight.BOLD,
                      color='#121212',
                  ),
                  ft.Text(
                      'Your completed M-Pesa purchases and pickup orders will'
                      ' appear here automatically.',
                      size=12,
                      color='#6B7280',
                      text_align=ft.TextAlign.CENTER,
                  ),
              ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
          )
      )
      return

    for ord in my_orders:
      items_detail = ft.Column(spacing=4)
      raw_items = ord.get('items', [])
      if isinstance(raw_items, str):
        try:
          raw_items = json.loads(raw_items)
        except Exception:
          raw_items = []
      if not isinstance(raw_items, list):
        raw_items = []

      for itm in raw_items:
        if not isinstance(itm, dict):
          continue
        qty = int(itm.get('qty') or itm.get('quantity') or 1)
        price = float(itm.get('price') or 0)
        items_detail.controls.append(
            ft.Row([
                ft.Text(
                    f"• {itm.get('name', 'Product')} (x{qty})",
                    size=11,
                    color='#4B5563',
                ),
                ft.Text(
                    f'KES {price * qty:,.0f}',
                    size=11,
                    color='#121212',
                    weight=ft.FontWeight.BOLD,
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

      status = ord.get('status', 'Pending PIN')
      badge_color = get_badge_color(status)
      order_id_display = ord.get('order_reference') or ord.get('order_id', 'N/A')
      order_date = ord.get('date', 'Recent')
      order_total = float(ord.get('total') or ord.get('total_amount') or 0)

      verify_btn = ft.Container()
      if status in ['Pending', 'Pending PIN']:
        verify_btn = ft.TextButton(
            'Check M-Pesa Status',
            icon=ft.icons.REFRESH,
            style=ft.ButtonStyle(color='#DC2626'),
            on_click=lambda e, ref=order_id_display: manual_verify_payment(ref),
        )

      order_card = ft.Container(
          bgcolor='#F9FAFB',
          border_radius=15,
          padding=15,
          border=ft.border.all(1, '#E5E7EB'),
          on_click=lambda e, current_order=ord: show_receipt_dialog(
              current_order
          ),
          content=ft.Column([
              ft.Row([
                  ft.Row([
                      ft.Icon(
                          ft.icons.RECEIPT_OUTLINED, size=16, color='#DC2626'
                      ),
                      ft.Text(
                          f'Order #{order_id_display}',
                          size=13,
                          weight=ft.FontWeight.BOLD,
                          color='#121212',
                      ),
                  ], spacing=6),
                  ft.Container(
                      bgcolor=badge_color,
                      padding=ft.padding.symmetric(horizontal=8, vertical=3),
                      border_radius=8,
                      content=ft.Text(
                          status,
                          size=10,
                          color='white',
                          weight=ft.FontWeight.BOLD,
                      ),
                  ),
              ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
              ft.Text(order_date, size=11, color='#9CA3AF'),
              ft.Divider(color='#E5E7EB'),
              items_detail,
              ft.Divider(color='#E5E7EB'),
              ft.Row([
                  ft.Text(
                      f"{ord.get('fulfillment', 'Pickup')} •"
                      f" {ord.get('payment_method', 'M-Pesa')}",
                      size=11,
                      color='#6B7280',
                  ),
                  ft.Text(
                      f'KES {order_total:,.0f}',
                      size=14,
                      weight=ft.FontWeight.BOLD,
                      color='#DC2626',
                  ),
              ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
              verify_btn,
              ft.Text(
                  'Tap to view full receipt',
                  size=10,
                  color='#9CA3AF',
                  italic=True,
              ),
          ], spacing=6),
      )
      orders_list_container.controls.append(order_card)

  def on_refresh_click(e):
    sync_orders_status()
    render_orders()
    page.update()

  def start_polling_loop():
    while True:
      time.sleep(3)
      changed = sync_orders_status()
      if changed:
        render_orders()
        page.update()

  # Initial load on view construct
  sync_orders_status()
  render_orders()
  threading.Thread(target=start_polling_loop, daemon=True).start()

  header_row = ft.Row([
      ft.Text(
          'My Orders', size=22, weight=ft.FontWeight.BOLD, color='#121212'
      ),
      ft.IconButton(
          icon=ft.icons.REFRESH,
          icon_color='#DC2626',
          tooltip='Refresh Status',
          on_click=on_refresh_click,
      ),
  ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

  return ft.Container(
      padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
      bgcolor='#FFFFFF',
      expand=True,
      content=ft.Column(
          [header_row, orders_list_container],
          scroll=ft.ScrollMode.AUTO,
          spacing=15,
      ),
  )