# app/ui/views/profile_view.py

import uuid
import flet as ft
import httpx
from app.ui.state import API_BASE_URL, cart, current_user_id, my_orders, user_info, wishlist
from app.ui.notifications import show_top_notification
import app.ui.state as app_state

current_logged_in_user = None

# Single shared FilePicker reused across settings-page rebuilds
_SHARED_FILE_PICKER = [None]

# Sub-page mode for the Hub tab: "" renders the dashboard, "settings" and "wishlist" render full pages
profile_page_mode = ""


def build_profile_view(page: ft.Page, switch_tab_callback, update_cart_callback, open_detail_callback=None):
  global current_logged_in_user, profile_page_mode

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

    app_state.current_user_id = user_id
    user_info['email'] = email
    current_logged_in_user = {'id': user_id, 'email': email}

    show_top_notification(page, '✅ Signed in successfully!', '#16A34A')
    switch_tab_callback(4)

  def handle_submit(e):
    email = (email_field.value or '').strip()
    password = (password_field.value or '').strip()

    if not email or not password:
      show_top_notification(page, '⚠️ Please enter email and password.', '#DC2626')
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
          show_top_notification(page, '🎉 Account created! You can now sign in below.', '#16A34A')
          toggle_mode(None)
        else:
          handle_login_success(data.get('user'))
      else:
        show_top_notification(page, data.get('detail', 'Authentication failed.'), '#DC2626')
    except Exception as err:
      show_top_notification(page, f'Connection error: {err}', '#DC2626')

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
    global current_logged_in_user, profile_page_mode
    current_logged_in_user = None
    profile_page_mode = ''
    app_state.current_user_id = ''
    user_info['email'] = ''
    # Clear per-user data so the next account never sees the previous one's data
    my_orders.clear()
    cart.clear()
    wishlist.clear()
    show_top_notification(page, '🔒 Signed out.', '#DC2626')
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

  # ==========================================================================
  # LOGGED IN VIEW
  # ==========================================================================

  # ---------------- PROFILE SETTINGS PAGE ----------------
  def build_settings_page():
    logged_in_email = current_logged_in_user.get('email', '')
    uid = current_logged_in_user.get('id', '')

    profile_data = {
        'username': 'Customer',
        'full_name': '',
        'birth_date': '',
        'gender': '',
        'phone': '',
        'avatar_url': '',
        'banner_url': '',
    }

    # Load existing profile from backend (best effort)
    try:
      if uid:
        pr = httpx.get(f'{API_BASE_URL}/auth/profile/{uid}', timeout=8)
        if pr.status_code == 200:
          data = pr.json()
          if isinstance(data, dict):
            for k in profile_data.keys():
              if data.get(k):
                profile_data[k] = str(data[k])
    except Exception as e:
      print(f'Profile load error: {e}')

    avatar_preview = ft.Container(
        width=72,
        height=72,
        border_radius=36,
        bgcolor='#FEE2E2',
        content=ft.Stack([
            ft.Container(
                expand=True,
                border_radius=36,
                bgcolor='#DC2626',
                alignment=ft.alignment.center,
                content=ft.Text(
                    (profile_data['username'] or profile_data['full_name'] or logged_in_email)[:2].upper(),
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color='white',
                ),
            ),
        ]),
        border=ft.border.all(3, 'white'),
        shadow=ft.BoxShadow(blur_radius=12, color='#30000000'),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    banner_preview = ft.Container(
        height=130,
        width=360,
        bgcolor='#121212',
        alignment=ft.alignment.center,
        border_radius=ft.border_radius.only(bottom_left=20, bottom_right=20),
        content=ft.Text('Add a banner photo', color='#9CA3AF', size=12),
    )

    def refresh_image_previews():
      if profile_data.get('avatar_url'):
        avatar_preview.content = ft.Container(
            expand=True, border_radius=36, bgcolor='#DC2626', clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            alignment=ft.alignment.center,
            content=ft.Image(src=profile_data['avatar_url'], fit=ft.ImageFit.COVER, width=72, height=72)
        )
      if profile_data.get('banner_url'):
        banner_preview.content = ft.Container(
            expand=True, bgcolor='#121212', clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(src=profile_data['banner_url'], fit=ft.ImageFit.COVER, width=360, height=130)
        )
      page.update()

    pending_upload = {'type': 'avatar'}

    def upload_selected(e):
      if not e.files or not e.files[0].path:
        return
      file_info = e.files[0]
      try:
        with open(file_info.path, 'rb') as f:
          content = f.read()
        res = httpx.post(
            f'{API_BASE_URL}/auth/upload-image/',
            params={'type': pending_upload['type']},
            files={'image': (file_info.name, content, file_info.content_type or 'image/jpeg')},
            timeout=15,
        )
        if res.status_code == 201:
          url = res.json().get('image_url', '')
          if pending_upload['type'] == 'avatar':
            profile_data['avatar_url'] = url
          else:
            profile_data['banner_url'] = url
          refresh_image_previews()
          show_top_notification(page, '🖼️ Photo uploaded!', '#16A34A')
        else:
          show_top_notification(page, '⚠️ Upload failed. Try again.', '#DC2626')
      except Exception as err:
        show_top_notification(page, f'Upload error: {err}', '#DC2626')

    file_picker = ft.FilePicker(on_result=upload_selected)
    existing_picker = _SHARED_FILE_PICKER[0]
    if existing_picker is not None:
      existing_picker.on_result = upload_selected
      file_picker = existing_picker
    else:
      _SHARED_FILE_PICKER[0] = file_picker
    if file_picker not in page.overlay:
      page.overlay.append(file_picker)

    def pick_avatar(e):
      pending_upload['type'] = 'avatar'
      file_picker.pick_files(allow_multiple=False, allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])

    def pick_banner(e):
      pending_upload['type'] = 'banner'
      file_picker.pick_files(allow_multiple=False, allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])

    username_field = ft.TextField(label='Username', value=profile_data['username'], border_color='#DC2626',
                                  text_size=13, height=44, bgcolor='white')
    fullname_field = ft.TextField(label='Full Name', value=profile_data['full_name'], border_color='#E5E7EB',
                                  text_size=13, height=44, bgcolor='white')
    birthdate_field = ft.TextField(label='Date of Birth', value=profile_data['birth_date'], border_color='#E5E7EB',
                                   hint_text='e.g. 1995-06-15', text_size=13, height=44, bgcolor='white')
    phone_field = ft.TextField(label='Phone Number', value=profile_data['phone'], border_color='#E5E7EB',
                               hint_text='e.g. 0712345678', text_size=13, height=44, bgcolor='white')
    gender_drop = ft.Dropdown(label='Gender', value=profile_data['gender'] or None, border_color='#E5E7EB',
                              text_size=13, bgcolor='white',
                              options=[ft.dropdown.Option(g) for g in ['Male', 'Female', 'Other']])
    email_display = ft.Text(logged_in_email, size=12, color='#6B7280')

    def save_profile(e):
      payload = {
          'username': (username_field.value or '').strip(),
          'full_name': (fullname_field.value or '').strip(),
          'birth_date': (birthdate_field.value or '').strip(),
          'gender': (gender_drop.value or '').strip(),
          'phone': (phone_field.value or '').strip(),
          'avatar_url': profile_data.get('avatar_url', ''),
          'banner_url': profile_data.get('banner_url', ''),
      }
      try:
        res = httpx.patch(
            f'{API_BASE_URL}/auth/profile/{uid}',
            json=payload,
            timeout=10,
        )
        if res.status_code in [200, 201]:
          if payload.get('full_name'):
            user_info['name'] = payload['full_name']
          if payload.get('phone'):
            user_info['phone'] = payload['phone']
          show_top_notification(page, '💾 Profile saved!', '#16A34A', ft.icons.SAVE_OUTLINED)
        else:
          show_top_notification(page, res.json().get('detail', 'Failed to save profile.'), '#DC2626')
      except Exception as err:
        show_top_notification(page, f'Save error: {err}', '#DC2626')

    refresh_image_previews()

    return ft.Container(
        padding=0,
        bgcolor='#FFFFFF',
        expand=True,
        content=ft.Column([
            banner_preview,
            ft.Stack([
                ft.Container(
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(top=-36),
                    content=ft.Stack([
                        avatar_preview,
                        ft.Container(
                            width=24,
                            height=24,
                            border_radius=12,
                            bgcolor='#DC2626',
                            alignment=ft.alignment.center,
                            left=-2,
                            bottom=-2,
                            content=ft.Icon(ft.icons.CAMERA_ALT, size=13, color='white'),
                        ),
                    ]),
                    on_click=pick_avatar,
                ),
            ]),
            ft.Row([
                ft.IconButton(ft.icons.ARROW_BACK, tooltip='Back to Hub', icon_color='#121212',
                              on_click=lambda e: back_to_hub()),
                ft.Text('Edit Profile', size=20, weight=ft.FontWeight.BOLD, color='#121212'),
                ft.Container(width=48),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(
                padding=ft.padding.only(left=15, right=15, bottom=120),
                content=ft.Column([
                    ft.Container(
                        bgcolor='#F9FAFB', padding=15, border_radius=15, border=ft.border.all(1, '#E5E7EB'),
                        content=ft.Column([
                            ft.Row([ft.Icon(ft.icons.PHOTO_CAMERA_OUTLINED, color='#DC2626', size=18),
                                    ft.Text('Profile Photo', size=13, weight=ft.FontWeight.BOLD, color='#121212'),
                                    ft.Container(width=8),
                                    ft.OutlinedButton('Upload Photo', icon=ft.icons.UPLOAD_FILE, height=32, text_size=12,
                                                       on_click=pick_avatar)], spacing=4),
                            ft.Divider(color='#E5E7EB', height=16),
                            ft.Row([ft.Icon(ft.icons.PHOTO_OUTLINED, color='#DC2626', size=18),
                                    ft.Text('Banner Photo', size=13, weight=ft.FontWeight.BOLD, color='#121212'),
                                    ft.Container(width=8),
                                    ft.OutlinedButton('Upload Banner', icon=ft.icons.UPLOAD_FILE, height=32, text_size=12,
                                                       on_click=pick_banner)], spacing=4),
                        ], spacing=6),
                    ),
                    ft.Text('Account Email', size=11, color='#6B7280'),
                    email_display,
                    ft.Divider(color='#E5E7EB', height=16),
                    username_field,
                    fullname_field,
                    birthdate_field,
                    phone_field,
                    gender_drop,
                    ft.Container(height=6),
                    ft.ElevatedButton(
                        'Save Changes', width=380, height=45, bgcolor='#DC2626', color='white',
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=save_profile,
                    ),
                ], spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
            ),
        ], spacing=0),
    )

  # ---------------- WISHLIST PAGE ----------------
  def build_wishlist_page():
    wishlist_col = ft.Column(spacing=10)

    if not wishlist:
      wishlist_col.controls.append(
          ft.Container(
              padding=40,
              alignment=ft.alignment.center,
              content=ft.Column([
                  ft.Icon(ft.icons.FAVORITE_BORDER, size=56, color='#9CA3AF'),
                  ft.Text('Your wishlist is empty.', size=14, color='#6B7280'),
                  ft.Text('Tap the heart on any part to save it here.', size=12, color='#9CA3AF'),
              ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
          )
      )
    else:
      for p_id, item in wishlist.items():
        img_url = str(item.get('image_url') or '') or \
            'https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png'
        wishlist_col.controls.append(
            ft.Container(
                bgcolor='#F9FAFB',
                border_radius=14,
                padding=10,
                border=ft.border.all(1, '#E5E7EB'),
                on_click=lambda e, it=item: open_wishlist_detail(it),
                content=ft.Row([
                    ft.Container(
                        width=52, height=52, border_radius=10, bgcolor='white',
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Image(src=img_url, fit=ft.ImageFit.COVER, width=52, height=52),
                    ),
                    ft.Column([
                        ft.Text(item.get('name', 'Product'), size=12, weight=ft.FontWeight.BOLD,
                                color='#121212', max_lines=1),
                        ft.Text(f"KES {float(item.get('price', 0)):,.0f}", size=12, color='#DC2626',
                                weight=ft.FontWeight.BOLD),
                    ], expand=True, spacing=2),
                    ft.IconButton(
                        ft.icons.FAVORITE, icon_color='#DC2626', icon_size=18, tooltip='Remove',
                        on_click=lambda e, it=item: remove_wishlist_item(it),
                    ),
                    ft.Icon(ft.icons.ARROW_FORWARD_IOS, size=14, color='#9CA3AF'),
                ], spacing=10),
            )
        )

    def open_wishlist_detail(item):
      if open_detail_callback:
        open_detail_callback(item)
      else:
        show_top_notification(page, 'Opening product not supported on this view.', '#DC2626')

    def remove_wishlist_item(item):
      if item.get('id') in wishlist:
        del wishlist[item['id']]
      switch_tab_callback(4)

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        bgcolor='#FFFFFF',
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.IconButton(ft.icons.ARROW_BACK, tooltip='Back to Hub', icon_color='#121212',
                              on_click=lambda e: back_to_hub()),
                ft.Text('My Wishlist', size=20, weight=ft.FontWeight.BOLD, color='#121212'),
                ft.Container(width=48),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(f'{len(wishlist)} saved part' + ('s' if len(wishlist) != 1 else ''),
                    size=12, color='#6B7280'),
            ft.Container(height=4),
            wishlist_col,
        ], spacing=8, scroll=ft.ScrollMode.AUTO),
    )

  def back_to_hub():
    global profile_page_mode
    profile_page_mode = ''
    switch_tab_callback(4)

  def open_settings():
    global profile_page_mode
    profile_page_mode = 'settings'
    switch_tab_callback(4)

  def open_wishlist_page():
    global profile_page_mode
    profile_page_mode = 'wishlist'
    switch_tab_callback(4)

  if profile_page_mode == 'settings':
    return build_settings_page()

  if profile_page_mode == 'wishlist':
    return build_wishlist_page()

  # ---------------- MAIN HUB DASHBOARD ----------------
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
              ft.Row([
                  ft.IconButton(
                      icon=ft.icons.SETTINGS_OUTLINED,
                      icon_color='#9CA3AF',
                      tooltip='Profile Settings',
                      on_click=lambda e: open_settings(),
                  ),
                  ft.IconButton(
                      icon=ft.icons.LOGOUT,
                      icon_color='#DC2626',
                      tooltip='Sign Out',
                      on_click=handle_logout,
                  ),
              ], spacing=0),
          ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
          ft.Row([
              ft.Container(
                  width=56,
                  height=56,
                  border_radius=28,
                  bgcolor='#DC2626',
                  alignment=ft.alignment.center,
                  border=ft.border.all(2, 'white'),
                  on_click=lambda e: open_settings(),
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
          'My Wishlist',
          'Spars you saved for later',
          ft.icons.FAVORITE_OUTLINE,
          f'{len(wishlist)} items' if wishlist else '',
          lambda e: open_wishlist_page(),
      ),
      hub_tile(
          'Profile Settings',
          'Photo, username & personal info',
          ft.icons.SETTINGS_OUTLINED,
          '',
          lambda e: open_settings(),
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
      img_url = str(item.get('image_url') or '') or \
          'https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png'
      wishlist_container.controls.append(
          ft.Container(
              padding=10,
              bgcolor='white',
              border_radius=10,
              border=ft.border.all(1, '#E5E7EB'),
              on_click=lambda e, it=item: (open_detail_callback(it) if open_detail_callback else None),
              content=ft.Row([
                  ft.Container(
                      width=44, height=44, border_radius=8, bgcolor='#F3F4F6',
                      clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                      content=ft.Image(src=img_url, fit=ft.ImageFit.COVER, width=44, height=44),
                  ),
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
                          switch_tab_callback(4),
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
          ft.Row([
              ft.Text(
                  'Saved Spares (Wishlist)',
                  size=14,
                  weight=ft.FontWeight.BOLD,
                  color='#121212',
              ),
              ft.TextButton(
                  'View All',
                  style=ft.ButtonStyle(color='#DC2626'),
                  on_click=lambda e: open_wishlist_page(),
              ),
          ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
          wishlist_container,
      ], scroll=ft.ScrollMode.AUTO, spacing=12),
  )