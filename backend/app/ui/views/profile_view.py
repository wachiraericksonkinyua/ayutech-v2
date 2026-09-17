# app/ui/views/profile_view.py

import flet as ft
import httpx
from app.ui.state import API_BASE_URL, cart, current_user_id, my_orders, user_info, wishlist

current_logged_in_user = None


def build_profile_view(page: ft.Page, switch_tab_callback, update_cart_callback):
  global current_logged_in_user

  def open_external_url(url: str):
    page.launch_url(url)

  MAPS_EXACT_URL = 'https://maps.app.goo.gl/iqoFy4be7SWYxCuJ8'

  # --- AUTHENTICATION STATE & FIELDS ---
  email_field = ft.TextField(
      label='Email Address',
      hint_text='you@example.com',
      border_color='#DC2626',
      focused_border_color='#DC2626',
      bgcolor='white',
      height=45,
      text_size=13,
      keyboard_type=ft.KeyboardType.EMAIL,
  )
  password_field = ft.TextField(
      label='Password',
      hint_text='Your secure password',
      border_color='#DC2626',
      focused_border_color='#DC2626',
      bgcolor='white',
      height=45,
      text_size=13,
      password=True,
      can_reveal_password=True,
  )

  is_register_mode = ft.Ref[bool]()
  is_register_mode.current = False

  title_text = ft.Text(
      'Welcome to AyuTech', size=20, weight=ft.FontWeight.BOLD, color='#121212'
  )
  subtitle_text = ft.Text(
      'Sign in to track orders & save garage spares.',
      size=12,
      color='#6B7280',
  )
  action_btn = ft.ElevatedButton(
      'Sign In',
      bgcolor='#DC2626',
      color='white',
      height=45,
      style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
  )
  switch_btn = ft.TextButton(
      'New here? Create an account', style=ft.ButtonStyle(color='#121212')
  )

  def handle_login_success(user_data):
    global current_logged_in_user
    user_dict = user_data if isinstance(user_data, dict) else {}
    email = user_dict.get('email') or getattr(user_data, 'email', '')
    user_id = str(
        user_dict.get('id')
        or user_dict.get('user_id')
        or getattr(user_data, 'id', '')
    )

    current_user_id = user_id
    user_info['email'] = email
    current_logged_in_user = {'id': user_id, 'email': email}

    page.snack_bar = ft.SnackBar(
        content=ft.Text('✅ Signed in successfully!'), bgcolor='#16A34A'
    )
    page.snack_bar.open = True
    page.update()
    switch_tab_callback(4)

  def handle_submit(e):
    email = (email_field.value or '').strip()
    password = (password_field.value or '').strip()

    if not email or not password:
      page.snack_bar = ft.SnackBar(
          content=ft.Text('⚠️ Please enter email and password.'),
          bgcolor='#DC2626',
      )
      page.snack_bar.open = True
      page.update()
      return

    endpoint = 'register' if is_register_mode.current else 'login'
    try:
      res = httpx.post(
          f'{API_BASE_URL}/auth/{endpoint}',
          json={'email': email, 'password': password},
          timeout=10,
      )
      data = res.json()
      if res.status_code == 200:
        if is_register_mode.current:
          page.snack_bar = ft.SnackBar(
              content=ft.Text(
                  '🎉 Account created! You can now sign in below.'
              ),
              bgcolor='#16A34A',
          )
          page.snack_bar.open = True
          page.update()
          toggle_mode(None)
        else:
          handle_login_success(data.get('user'))
      else:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(data.get('detail', 'Authentication failed.')),
            bgcolor='#DC2626',
        )
        page.snack_bar.open = True
        page.update()
    except Exception as err:
      page.snack_bar = ft.SnackBar(
          content=ft.Text(f'Connection error: {err}'), bgcolor='#DC2626'
      )
      page.snack_bar.open = True
      page.update()

  action_btn.on_click = handle_submit

  def toggle_mode(e):
    is_register_mode.current = not is_register_mode.current
    if is_register_mode.current:
      title_text.value = 'Create Garage Account'
      subtitle_text.value = 'Register to track orders & save items.'
      action_btn.text = 'Register Account'
      switch_btn.text = 'Already have an account? Sign In'
    else:
      title_text.value = 'Welcome to AyuTech'
      subtitle_text.value = 'Sign in to track orders & save garage spares.'
      action_btn.text = 'Sign In'
      switch_btn.text = 'New here? Create an account'
    page.update()

  switch_btn.on_click = toggle_mode

  def handle_logout(e):
    global current_logged_in_user
    current_logged_in_user = None
    from app.ui.state import current_user_id as cu_id

    global current_user_id
    current_user_id = ''
    user_info['email'] = ''
    # Clear per-user data so the next account never sees the previous one's data
    my_orders.clear()
    cart.clear()
    wishlist.clear()
    page.snack_bar = ft.SnackBar(
        content=ft.Text('🔒 Signed out.'), bgcolor='#DC2626'
    )
    page.snack_bar.open = True
    page.update()
    switch_tab_callback(4)

  # --- GUEST VIEW (PROMPT TO LOGIN) ---
  if not current_logged_in_user:
    return ft.Container(
        padding=20,
        bgcolor='#FFFFFF',
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column([
            ft.Container(
                padding=22,
                bgcolor='#F9FAFB',
                border_radius=20,
                border=ft.border.all(1, '#E5E7EB'),
                width=360,
                content=ft.Column([
                    ft.Row(
                        [
                            ft.Container(
                                width=44,
                                height=44,
                                bgcolor='#FEE2E2',
                                border_radius=22,
                                alignment=ft.alignment.center,
                                content=ft.Icon(
                                    ft.icons.LOCK_PERSON_OUTLINED,
                                    color='#DC2626',
                                    size=20,
                                ),
                            ),
                            ft.Column(
                                [
                                    title_text,
                                    subtitle_text,
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Divider(color='#E5E7EB', height=20),
                    email_field,
                    password_field,
                    ft.Container(height=4),
                    action_btn,
                    ft.Container(
                        alignment=ft.alignment.center, content=switch_btn
                    ),
                ], spacing=12),
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
    )

  # --- LOGGED IN PROFILE HUB (PINTEREST STYLE) ---
  logged_in_email = current_logged_in_user.get('email', 'Customer')

  profile_header = ft.Container(
      bgcolor='#121212',
      border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
      padding=20,
      content=ft.Column([
          ft.Row([
              ft.Text(
                  'My Garage Hub',
                  size=15,
                  weight=ft.FontWeight.BOLD,
                  color='white',
              ),
              ft.IconButton(
                  icon=ft.icons.LOGOUT,
                  icon_color='#DC2626',
                  tooltip='Sign Out',
                  on_click=handle_logout,
              ),
          ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
          ft.Row([
              ft.Container(
                  width=56,
                  height=56,
                  border_radius=28,
                  bgcolor='#DC2626',
                  alignment=ft.alignment.center,
                  border=ft.border.all(2, 'white'),
                  content=ft.Text(
                      logged_in_email[:2].upper(),
                      size=18,
                      weight=ft.FontWeight.BOLD,
                      color='white',
                  ),
              ),
              ft.Column([
                  ft.Text(
                      logged_in_email.split('@')[0].capitalize(),
                      size=16,
                      weight=ft.FontWeight.BOLD,
                      color='white',
                  ),
                  ft.Text(logged_in_email, size=11, color='#9CA3AF'),
              ], spacing=2),
          ], spacing=14),
      ], spacing=10),
  )

  def hub_tile(title, subtitle, icon, badge, on_click):
    return ft.Container(
        bgcolor='#F9FAFB',
        border_radius=12,
        padding=12,
        border=ft.border.all(1, '#E5E7EB'),
        on_click=on_click,
        content=ft.Row([
            ft.Row([
                ft.Container(
                    width=36,
                    height=36,
                    bgcolor='#FEE2E2',
                    border_radius=10,
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color='#DC2626', size=18),
                ),
                ft.Column([
                    ft.Text(
                        title,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color='#121212',
                    ),
                    ft.Text(subtitle, size=11, color='#6B7280'),
                ], spacing=2),
            ], spacing=12),
            ft.Row([
                ft.Container(
                    bgcolor='#E5E7EB',
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    content=ft.Text(
                        badge,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color='#121212',
                    ),
                )
                if badge
                else ft.Container(),
                ft.Icon(
                    ft.icons.ARROW_FORWARD_IOS, size=14, color='#9CA3AF'
                ),
            ], spacing=6),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
    )

  nav_tiles = ft.Column([
      hub_tile(
          'Track Orders',
          'Check M-Pesa status & receipts',
          ft.icons.LOCAL_SHIPPING_OUTLINED,
          'Live',
          lambda e: switch_tab_callback(3),
      ),
      hub_tile(
          'Shopping Cart',
          'View selected parts & checkout',
          ft.icons.SHOPPING_BAG_OUTLINED,
          f'{len(cart)} items' if cart else '',
          lambda e: switch_tab_callback(2),
      ),
      hub_tile(
          'Parts Catalog',
          'Browse Japanese & heavy spares',
          ft.icons.GRID_VIEW_OUTLINED,
          '',
          lambda e: switch_tab_callback(1),
      ),
      hub_tile(
          'Kirinyaga Road Shop',
          'Get GPS directions & store hours',
          ft.icons.STORE_OUTLINED,
          'Open',
          lambda e: open_external_url(MAPS_EXACT_URL),
      ),
  ], spacing=10)

  wishlist_container = ft.Column(spacing=8)

  def render_wishlist():
    wishlist_container.controls.clear()
    if not wishlist:
      wishlist_container.controls.append(
          ft.Container(
              padding=14,
              bgcolor='#F9FAFB',
              border_radius=12,
              border=ft.border.all(1, '#E5E7EB'),
              content=ft.Text(
                  'No saved spare parts in your wishlist yet.',
                  size=12,
                  color='#6B7280',
              ),
          )
      )
      return

    for p_id, item in wishlist.items():
      wishlist_container.controls.append(
          ft.Container(
              padding=10,
              bgcolor='white',
              border_radius=10,
              border=ft.border.all(1, '#E5E7EB'),
              content=ft.Row([
                  ft.Column([
                      ft.Text(
                          item.get('name', 'Product'),
                          size=12,
                          weight=ft.FontWeight.BOLD,
                          color='#121212',
                          max_lines=1,
                      ),
                      ft.Text(
                          f"KES {float(item.get('price', 0)):,.0f}",
                          size=11,
                          color='#DC2626',
                          weight=ft.FontWeight.BOLD,
                      ),
                  ], expand=True),
                  ft.IconButton(
                      icon=ft.icons.ADD_SHOPPING_CART,
                      icon_color='#DC2626',
                      tooltip='Add to Cart',
                      on_click=lambda e, prod=item: (
                          update_cart_callback(prod, 1),
                          page.show_snack_bar(
                              ft.SnackBar(
                                  ft.Text('Item added to cart'), bgcolor='#121212'
                              )
                          ),
                      ),
                  ),
              ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
          )
      )

  render_wishlist()

  return ft.Container(
      padding=ft.padding.only(left=15, right=15, top=0, bottom=120),
      bgcolor='#FFFFFF',
      expand=True,
      content=ft.Column([
          profile_header,
          ft.Container(height=10),
          ft.Text(
              'Garage Dashboard',
              size=14,
              weight=ft.FontWeight.BOLD,
              color='#121212',
          ),
          nav_tiles,
          ft.Divider(color='#E5E7EB', height=20),
          ft.Text(
              'Saved Spares (Wishlist)',
              size=14,
              weight=ft.FontWeight.BOLD,
              color='#121212',
          ),
          wishlist_container,
      ], scroll=ft.ScrollMode.AUTO, spacing=12),
  )