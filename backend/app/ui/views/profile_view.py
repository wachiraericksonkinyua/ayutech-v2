# app/ui/views/profile_view.py

import uuid
import flet as ft
import httpx
from app.ui.state import API_BASE_URL, cart, current_user_id, my_orders, user_info, wishlist
from app.ui.notifications import notify, show_top_notification
from app.ui import theme as theme_mod
from app.ui.views.track_view import build_track_page
from app.ui import colors as C
from app.ui import api as api_client
import app.ui.state as app_state

current_logged_in_user = None

# Single shared FilePicker reused across settings-page rebuilds
_SHARED_FILE_PICKER = [None]

# Sub-page mode for the Hub tab. "" renders the dashboard; other values render
# dedicated full pages: settings, wishlist, track, forgot, reset, onboarding.
profile_page_mode = ""

# Opaque token handed back by the backend reset callback (kept out of the URL
# once captured) and the email awaiting a reset link.
pending_reset_token = ""
pending_reset_email = ""

# Shared profile info so the Hub header reflects saved avatar/name immediately
hub_profile = {'username': 'Customer', 'full_name': '', 'phone': '', 'avatar_url': ''}


def apply_login(user_data, page=None):
    """Set the global signed-in user from an auth response payload."""
    global current_logged_in_user
    user_dict = user_data if isinstance(user_data, dict) else {}
    email = user_dict.get('email') or getattr(user_data, 'email', '') or ''
    user_id = str(
        user_dict.get('id')
        or user_dict.get('user_id')
        or getattr(user_data, 'id', '')
        or ''
    )
    app_state.current_user_id = user_id
    user_info['email'] = email
    current_logged_in_user = {'id': user_id, 'email': email}
    return current_logged_in_user


def is_profile_incomplete(user_id) -> bool:
    """True when phone/date-of-birth are still missing (first-time sign-up)."""
    if not user_id:
        return False
    try:
        res = api_client.get(f'/auth/profile/{user_id}')
        if res.status_code != 200:
            return False
        data = res.json()
        if not isinstance(data, dict):
            return False
        return not (str(data.get('phone') or '').strip()
                    or str(data.get('birth_date') or '').strip())
    except Exception:
        return False


def build_profile_view(page: ft.Page, switch_tab_callback, update_cart_callback, open_detail_callback=None):
  global current_logged_in_user, profile_page_mode

  def open_external_url(url: str):
    page.launch_url(url)

  MAPS_EXACT_URL = 'https://maps.app.goo.gl/iqoFy4be7SWYxCuJ8'

  # --- AUTHENTICATION STATE & FIELDS ---
  email_field = ft.TextField(
      label='Email Address',
      hint_text='you@example.com',
      border_color=C.accent(),
      focused_border_color=C.accent(),
      bgcolor=C.field(),
      height=45,
      text_size=13,
      keyboard_type=ft.KeyboardType.EMAIL,
  )
  password_field = ft.TextField(
      label='Password',
      hint_text='Your secure password',
      border_color=C.accent(),
      focused_border_color=C.accent(),
      bgcolor=C.field(),
      height=45,
      text_size=13,
      password=True,
      can_reveal_password=True,
  )

  is_register_mode = ft.Ref[bool]()
  is_register_mode.current = False

  title_text = ft.Text(
      'Welcome to AyuTech', size=20, weight=ft.FontWeight.BOLD, color=C.text()
  )
  subtitle_text = ft.Text(
      'Sign in to track orders & save garage spares.',
      size=12,
      color=C.soft(),
  )
  action_btn = ft.ElevatedButton(
      'Sign In',
      bgcolor=C.accent(),
      color='white',
      height=45,
      style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
  )
  switch_btn = ft.TextButton(
      'New here? Create an account', style=ft.ButtonStyle(color=C.text())
  )

  def handle_login_success(user_data, check_onboarding=True):
    global profile_page_mode
    logged = apply_login(user_data, page)
    email = logged['email']

    # First-time sign-ups (e.g. Google) have no phone / date of birth yet:
    # send them straight to the profile enrichment step.
    if check_onboarding and is_profile_incomplete(logged['id']):
      profile_page_mode = 'onboarding'
      notify(page, 'Almost there! Add a few details to finish your profile.', '#2563EB', ft.icons.BADGE_OUTLINED, title='Welcome to AyuTech')
    else:
      profile_page_mode = ''
      notify(page, 'Signed in successfully!', '#16A34A', title='Welcome Back')
    switch_tab_callback(4)

  def handle_submit(e):
    email = (email_field.value or '').strip()
    password = (password_field.value or '').strip()

    if not email or not password:
      show_top_notification(page, '⚠️ Please enter email and password.', C.accent())
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
          app_state.access_token = data.get('access_token', '') or ''
          handle_login_success(data.get('user'))
      else:
        show_top_notification(page, data.get('detail', 'Authentication failed.'), C.accent())
    except Exception as err:
      show_top_notification(page, f'Connection error: {err}', C.accent())

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
    app_state.access_token = ''
    user_info['email'] = ''
    # Clear per-user data so the next account never sees the previous one's data
    my_orders.clear()
    cart.clear()
    wishlist.clear()
    notify(page, 'Signed out. See you soon!', C.accent(), title='Signed Out')
    switch_tab_callback(4)

  # --- GUEST VIEW (PROMPT TO LOGIN) ---
  def reset_to_hub_guest():
    global profile_page_mode
    profile_page_mode = ''
    switch_tab_callback(4)

  def open_track_guest():
    global profile_page_mode
    profile_page_mode = 'track'
    switch_tab_callback(4)

  def open_forgot_page(e=None):
    global profile_page_mode
    profile_page_mode = 'forgot'
    switch_tab_callback(4)

  def open_reset_page(e=None):
    global profile_page_mode
    profile_page_mode = 'reset'
    switch_tab_callback(4)

  def back_to_login(e=None):
    global profile_page_mode
    profile_page_mode = ''
    switch_tab_callback(4)

  def build_forgot_page():
    """Dedicated view: request a Supabase recovery email link."""
    reset_email = ft.TextField(
        label='Your account email',
        hint_text='you@example.com',
        border_color=C.input_border(),
        focused_border_color=C.accent(),
        bgcolor=C.field(),
        color=C.text(),
        height=45,
        text_size=13,
        keyboard_type=ft.KeyboardType.EMAIL,
    )
    status_text = ft.Text('', size=12, color=C.soft())

    def send_reset(ev):
      val = (reset_email.value or '').strip()
      if not val:
        show_top_notification(page, '⚠️ Please enter your email.', C.accent())
        return
      status_text.value = 'Sending…'
      status_text.color = C.soft()
      page.update()
      try:
        httpx.post(
            f'{API_BASE_URL}/auth/forgot-password',
            json={'email': val},
            timeout=20,
        )
        global pending_reset_email
        pending_reset_email = val
        status_text.value = 'If that email is registered, a reset link is on its way.'
        status_text.color = C.success()
        notify(page, 'Check your inbox for the secure reset link.', '#16A34A', ft.icons.MARK_EMAIL_READ, title='Email sent')
      except Exception as err:
        status_text.value = f'Error: {err}'
        status_text.color = C.danger()
      page.update()

    return ft.Container(
        padding=20,
        bgcolor=C.bg(),
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column([
            ft.Container(
                padding=22,
                bgcolor=C.surface(),
                border_radius=20,
                border=ft.border.all(1, C.divider()),
                width=360,
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(ft.icons.ARROW_BACK, icon_color=C.text(),
                                      tooltip='Back to sign in', on_click=back_to_login),
                        ft.Container(
                            width=40, height=40, bgcolor=C.accent_soft(), border_radius=20,
                            alignment=ft.alignment.center,
                            content=ft.Icon(ft.icons.LOCK_RESET, color=C.accent(), size=20),
                        ),
                        ft.Text('Reset Password', size=17, weight=ft.FontWeight.BOLD, color=C.text()),
                    ], spacing=8),
                    ft.Text('Enter your email and we will send a secure link to choose a new password.',
                            size=12, color=C.soft()),
                    reset_email,
                    ft.ElevatedButton(
                        'Send reset link', width=316, height=45,
                        bgcolor=C.accent(), color=C.on_accent(),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=send_reset,
                    ),
                    status_text,
                ], spacing=12),
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )

  def build_reset_page():
    """Dedicated view: set a new password using a validated reset token."""
    token = pending_reset_token
    new_password = ft.TextField(
        label='New password',
        hint_text='At least 6 characters',
        border_color=C.input_border(),
        focused_border_color=C.accent(),
        bgcolor=C.field(),
        color=C.text(),
        height=45,
        text_size=13,
        password=True,
        can_reveal_password=True,
    )
    confirm_password = ft.TextField(
        label='Confirm new password',
        hint_text='Repeat the password',
        border_color=C.input_border(),
        focused_border_color=C.accent(),
        bgcolor=C.field(),
        color=C.text(),
        height=45,
        text_size=13,
        password=True,
        can_reveal_password=True,
    )
    status_text = ft.Text('', size=12, color=C.soft())

    def save_new_password(ev):
      pwd = (new_password.value or '').strip()
      confirm = (confirm_password.value or '').strip()
      if len(pwd) < 6:
        status_text.value = 'Password must be at least 6 characters.'
        status_text.color = C.danger()
        page.update()
        return
      if pwd != confirm:
        status_text.value = 'Passwords do not match.'
        status_text.color = C.danger()
        page.update()
        return
      status_text.value = 'Updating password…'
      status_text.color = C.soft()
      page.update()
      try:
        res = httpx.post(
            f'{API_BASE_URL}/auth/reset-password',
            json={'token': token, 'new_password': pwd},
            timeout=20,
        )
        data = res.json() if res.content else {}
        if res.status_code == 200:
          global pending_reset_token
          pending_reset_token = ''
          notify(page, 'Password updated. Please sign in.', '#16A34A', ft.icons.CHECK_CIRCLE, title='Password reset')
          back_to_login()
        else:
          status_text.value = data.get('detail', 'Could not update password.')
          status_text.color = C.danger()
          page.update()
      except Exception as err:
        status_text.value = f'Error: {err}'
        status_text.color = C.danger()
        page.update()

    if not token:
      return ft.Container(
          padding=20, bgcolor=C.bg(), alignment=ft.alignment.center, expand=True,
          content=ft.Column([
              ft.Icon(ft.icons.LINK_OFF, size=48, color=C.muted()),
              ft.Text('This reset link is invalid or has expired.', size=14, color=C.text()),
              ft.ElevatedButton('Request a new link', bgcolor=C.accent(), color=C.on_accent(),
                                on_click=open_forgot_page),
          ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
      )

    return ft.Container(
        padding=20,
        bgcolor=C.bg(),
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column([
            ft.Container(
                padding=22,
                bgcolor=C.surface(),
                border_radius=20,
                border=ft.border.all(1, C.divider()),
                width=360,
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            width=40, height=40, bgcolor=C.accent_soft(), border_radius=20,
                            alignment=ft.alignment.center,
                            content=ft.Icon(ft.icons.PASSWORD, color=C.accent(), size=20),
                        ),
                        ft.Text('Choose a new password', size=17, weight=ft.FontWeight.BOLD, color=C.text()),
                    ], spacing=8),
                    ft.Text('Your reset link is verified. Set a strong new password below.',
                            size=12, color=C.soft()),
                    new_password,
                    confirm_password,
                    ft.ElevatedButton(
                        'Save new password', width=316, height=45,
                        bgcolor=C.accent(), color=C.on_accent(),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=save_new_password,
                    ),
                    status_text,
                ], spacing=12),
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )

  def handle_google_login(e):
    import threading
    import app.ui.oauth as oauth

    is_web = bool(getattr(page, 'web', False))

    # --- Web app: let the backend own the callback -------------------------
    # Supabase redirects to /auth/oauth-callback, which exchanges the code and
    # bounces the browser back into the app with a one-time login token that
    # main_app consumes on startup. No localhost listener needed.
    if is_web:
      def _start_web():
        try:
          res = httpx.post(
              f'{API_BASE_URL}/auth/oauth-url',
              json={'provider': 'google'},
              timeout=20,
          )
          data = res.json() if res.content else {}
          url = data.get('url', '')
          if not url:
            show_top_notification(page, data.get('detail', 'Could not start Google sign-in.'), C.accent())
            return
          page.launch_url(url)
        except Exception as err:
          show_top_notification(page, f'Google sign-in error: {err}', C.accent())

      show_top_notification(page, 'Redirecting to Google…', '#2563EB')
      threading.Thread(target=_start_web, daemon=True).start()
      return

    # --- Desktop: capture the redirect with a one-shot local listener ------
    server = oauth.OAuthCallbackServer()
    try:
      server.start()
    except Exception as err:
      show_top_notification(page, f'Could not start sign-in listener: {err}', C.accent())
      return

    def _run():
      try:
        res = httpx.post(
            f'{API_BASE_URL}/auth/oauth-url',
            json={'provider': 'google', 'redirect_to': oauth.REDIRECT_URI},
            timeout=15,
        )
        data = res.json() if res.content else {}
        url = data.get('url', '')
        verifier = data.get('code_verifier', '')
        if not url:
          show_top_notification(page, 'Could not start Google sign-in.', C.accent())
          return
        try:
          page.launch_url(url)
        except Exception:
          pass
        params = server.wait(timeout=180)
        if not params or not params.get('code'):
          show_top_notification(page, 'Google sign-in was cancelled or timed out.', C.accent())
          return
        code = params['code'][0]
        ex = httpx.post(
            f'{API_BASE_URL}/auth/oauth-exchange',
            json={'code': code, 'code_verifier': verifier, 'redirect_to': oauth.REDIRECT_URI},
            timeout=25,
        )
        exd = ex.json() if ex.content else {}
        if ex.status_code == 200:
          app_state.access_token = exd.get('access_token', '') or ''
          handle_login_success(exd.get('user'))
        else:
          show_top_notification(page, exd.get('detail', 'Google sign-in failed.'), C.accent())
      except Exception as err:
        show_top_notification(page, f'Google sign-in error: {err}', C.accent())
      finally:
        server.stop()

    show_top_notification(page, 'Complete sign-in in your browser…', '#2563EB')
    threading.Thread(target=_run, daemon=True).start()

  # Password recovery works whether or not the user is signed in, so these
  # dedicated views are resolved before the guest/login gate.
  if profile_page_mode == 'forgot':
    return build_forgot_page()
  if profile_page_mode == 'reset':
    return build_reset_page()

  if not current_logged_in_user:
    if profile_page_mode == 'track':
      return build_track_page(page, reset_to_hub_guest)
    return ft.Container(
        padding=20,
        bgcolor=C.bg(),
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column([
            ft.Container(
                padding=22,
                bgcolor=C.surface(),
                border_radius=20,
                border=ft.border.all(1, C.divider()),
                width=360,
                content=ft.Column([
                    ft.Row(
                        [
                            ft.Container(
                                width=44,
                                height=44,
                                bgcolor=C.accent_soft(),
                                border_radius=22,
                                alignment=ft.alignment.center,
                                content=ft.Icon(
                                    ft.icons.LOCK_PERSON_OUTLINED,
                                    color=C.accent(),
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
                    ft.Divider(color=C.divider(), height=20),
                    email_field,
                    password_field,
                    ft.Container(height=4),
                    action_btn,
                    ft.Container(
                        alignment=ft.alignment.center, content=switch_btn
                    ),
                    ft.Container(
                        alignment=ft.alignment.center,
                        content=ft.TextButton(
                            'Forgot password?',
                            style=ft.ButtonStyle(color=C.soft()),
                            on_click=open_forgot_page,
                        ),
                    ),
                    ft.Row([
                        ft.Container(expand=True, content=ft.Divider(color=C.divider())),
                        ft.Text('or', size=11, color=C.muted()),
                        ft.Container(expand=True, content=ft.Divider(color=C.divider())),
                    ], spacing=8),
                    ft.OutlinedButton(
                        'Continue with Google',
                        icon=ft.icons.LOGIN,
                        width=316,
                        height=44,
                        style=ft.ButtonStyle(
                            color=C.text(),
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=handle_google_login,
                    ),
                    ft.Divider(color=C.divider(), height=12),
                    ft.TextButton(
                        'Track an order without signing in',
                        icon=ft.icons.LOCAL_SHIPPING_OUTLINED,
                        style=ft.ButtonStyle(color=C.accent()),
                        on_click=lambda e: open_track_guest(),
                    ),
                ], spacing=12),
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
    )

  # ==========================================================================
  # LOGGED IN VIEW
  # ==========================================================================

  # ---------------- FIRST-TIME PROFILE ONBOARDING ----------------
  def build_onboarding_page():
    """Collect phone (M-Pesa / order notifications) and date of birth."""
    uid = current_logged_in_user.get('id', '')
    email = current_logged_in_user.get('email', '')

    fullname_field = ft.TextField(
        label='Full Name', border_color=C.input_border(), focused_border_color=C.accent(),
        text_size=13, height=44, bgcolor=C.field(), color=C.text(),
        value=(hub_profile.get('full_name') or ''),
    )
    phone_field = ft.TextField(
        label='Phone Number', hint_text='e.g. 0712345678',
        border_color=C.input_border(), focused_border_color=C.accent(),
        text_size=13, height=44, bgcolor=C.field(), color=C.text(),
        keyboard_type=ft.KeyboardType.PHONE,
        value=(hub_profile.get('phone') or ''),
    )
    birthdate_field = ft.TextField(
        label='Date of Birth', hint_text='e.g. 1995-06-15',
        border_color=C.input_border(), focused_border_color=C.accent(),
        text_size=13, height=44, bgcolor=C.field(), color=C.text(),
    )
    gender_drop = ft.Dropdown(
        label='Gender', border_color=C.input_border(), text_size=13, bgcolor=C.field(),
        color=C.text(),
        options=[ft.dropdown.Option(g) for g in ['Male', 'Female', 'Other']],
    )
    status_text = ft.Text('', size=12, color=C.soft())

    def finish(skip=False):
      global profile_page_mode
      if not skip:
        payload = {
            'full_name': (fullname_field.value or '').strip(),
            'phone': (phone_field.value or '').strip(),
            'birth_date': (birthdate_field.value or '').strip(),
            'gender': (gender_drop.value or '').strip(),
        }
        if not payload['phone']:
          status_text.value = 'Please add a phone number so we can send M-Pesa and order updates.'
          status_text.color = C.danger()
          page.update()
          return
        try:
          res = api_client.patch(f'/auth/profile/{uid}', json=payload, timeout=10)
          if res.status_code not in [200, 201]:
            detail = 'Could not save your details. You can add them later in Settings.'
            try:
              detail = res.json().get('detail', detail)
            except Exception:
              pass
            status_text.value = detail
            status_text.color = C.danger()
            page.update()
            return
          hub_profile['full_name'] = payload['full_name']
          hub_profile['phone'] = payload['phone']
          user_info['phone'] = payload['phone']
          if payload['full_name']:
            user_info['name'] = payload['full_name']
          notify(page, 'Profile complete. Welcome to AyuTech!', '#16A34A', ft.icons.CHECK_CIRCLE, title='All set')
        except Exception as err:
          status_text.value = f'Connection error: {err}'
          status_text.color = C.danger()
          page.update()
          return
      profile_page_mode = ''
      switch_tab_callback(4)

    return ft.Container(
        padding=20,
        bgcolor=C.bg(),
        expand=True,
        alignment=ft.alignment.top_center,
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=44, height=44, bgcolor=C.accent_soft(), border_radius=22,
                    alignment=ft.alignment.center,
                    content=ft.Icon(ft.icons.PERSON_ADD_ALT_1, color=C.accent(), size=20),
                ),
                ft.Column([
                    ft.Text('Complete your profile', size=18, weight=ft.FontWeight.BOLD, color=C.text()),
                    ft.Text(email, size=11, color=C.soft()),
                ], spacing=2, expand=True),
            ], spacing=12),
            ft.Text('Add a phone number for M-Pesa receipts and order notifications. Date of birth is optional.',
                    size=12, color=C.soft()),
            ft.Divider(color=C.divider(), height=8),
            fullname_field,
            phone_field,
            birthdate_field,
            gender_drop,
            status_text,
            ft.ElevatedButton(
                'Save & Continue', width=380, height=46,
                bgcolor=C.accent(), color=C.on_accent(),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                on_click=lambda e: finish(skip=False),
            ),
            ft.TextButton(
                'Skip for now', style=ft.ButtonStyle(color=C.soft()),
                on_click=lambda e: finish(skip=True),
            ),
        ], spacing=12, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )

  if profile_page_mode == 'onboarding':
    return build_onboarding_page()

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
        'addresses': [],
    }

    avatar_preview = ft.Container(
        width=72,
        height=72,
        border_radius=36,
        bgcolor=C.accent_soft(),
        content=ft.Stack([
            ft.Container(
                expand=True,
                border_radius=36,
                bgcolor=C.accent(),
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
        bgcolor=C.text(),
        alignment=ft.alignment.center,
        border_radius=ft.border_radius.only(bottom_left=20, bottom_right=20),
        content=ft.Text('Add a banner photo', color=C.muted(), size=12),
    )

    def refresh_image_previews():
      if profile_data.get('avatar_url'):
        avatar_preview.content = ft.Container(
            expand=True, border_radius=36, bgcolor=C.accent(), clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            alignment=ft.alignment.center,
            content=ft.Image(src=profile_data['avatar_url'], fit=ft.ImageFit.COVER, width=72, height=72)
        )
      else:
        avatar_preview.content = ft.Container(
            expand=True, border_radius=36, bgcolor=C.accent(), clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            alignment=ft.alignment.center,
            content=ft.Text(
                (profile_data['username'] or profile_data['full_name'] or logged_in_email)[:2].upper(),
                size=20, weight=ft.FontWeight.BOLD, color='white',
            ),
        )
      if profile_data.get('banner_url'):
        banner_preview.content = ft.Container(
            expand=True, bgcolor=C.text(), clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(src=profile_data['banner_url'], fit=ft.ImageFit.COVER, width=360, height=130)
        )
      try:
        username_field.value = profile_data.get('username', '')
        fullname_field.value = profile_data.get('full_name', '')
        phone_field.value = profile_data.get('phone', '')
        page.update()
      except Exception:
        pass

    def load_profile_async():
      import threading

      def _load():
        try:
          if uid:
            pr = api_client.get(f'/auth/profile/{uid}')
            if pr.status_code == 200:
              data = pr.json()
              if isinstance(data, dict):
                for k in profile_data.keys():
                  if data.get(k) is not None:
                    profile_data[k] = data[k] if isinstance(data[k], list) else str(data[k])
                hub_profile['avatar_url'] = profile_data.get('avatar_url', '')
                hub_profile['full_name'] = profile_data.get('full_name', '')
                hub_profile['username'] = profile_data.get('username', '')
                hub_profile['phone'] = profile_data.get('phone', '')
                refresh_image_previews()
                try:
                  render_addresses()
                except Exception:
                  pass
        except Exception as e:
          print(f'Profile load error: {e}')

      threading.Thread(target=_load, daemon=True).start()

    def change_theme(e):
      theme_mod.apply_theme(page, theme_drop.value or 'system')
      notify(page, f'Theme set to {theme_drop.value.title()}', '#16A34A', ft.icons.BRIGHTNESS_6_OUTLINED, title='Appearance')
      # Rebuild settings so every themed token refreshes immediately.
      switch_tab_callback(4)

    theme_drop = ft.Dropdown(
        label='App Theme', value=app_state.theme_mode, border_color=C.input_border(),
        text_size=13, bgcolor=C.field(), on_change=change_theme,
        options=[ft.dropdown.Option(m) for m in ['system', 'light', 'dark']],
        hint_text='Follow my PC / Phone',
    )

    addresses_col = ft.Column(spacing=8)
    addresses_input = ft.TextField(
        label='Add a delivery address', hint_text='e.g. Diamond Plaza, 4th Floor, Moi Avenue, Nairobi',
        border_color=C.input_border(), text_size=13, height=44, bgcolor=C.field(),
    )

    def render_addresses():
      addresses_col.controls.clear()
      addrs = [a for a in (profile_data.get('addresses') or []) if a]
      if not addrs:
        addresses_col.controls.append(
            ft.Text('No saved addresses yet.', size=11, color=C.muted()),
        )
        return
      for idx, addr in enumerate(addrs):
        row = ft.Row([
            ft.Icon(ft.icons.LOCATION_ON_OUTLINED, size=16, color=C.accent()),
            ft.Text(str(addr), size=12, color=C.text(), expand=True, max_lines=2),
            ft.IconButton(
                ft.icons.DELETE_OUTLINE, icon_size=16, icon_color=C.accent(),
                tooltip='Remove address',
                on_click=lambda e, i=idx: remove_address(i),
            ),
        ], spacing=8)
        addresses_col.controls.append(
            ft.Container(bgcolor=C.surface(), border_radius=10, padding=ft.padding.symmetric(horizontal=10, vertical=4),
                         border=ft.border.all(1, C.divider()), content=row)
        )

    def remove_address(idx):
      addrs = [a for a in (profile_data.get('addresses') or []) if a]
      if 0 <= idx < len(addrs):
        del addrs[idx]
        profile_data['addresses'] = addrs
      render_addresses()
      page.update()

    def add_address(e):
      val = (addresses_input.value or '').strip()
      if not val:
        return
      addrs = [a for a in (profile_data.get('addresses') or []) if a]
      if val in addrs:
        notify(page, 'Address already saved.', C.accent(), ft.icons.ERROR_OUTLINE, title='Duplicate Address')
        return
      addrs.append(val)
      profile_data['addresses'] = addrs
      addresses_input.value = ''
      render_addresses()
      page.update()

    pending_upload = {'type': 'avatar'}

    def upload_selected(e):
      if not e.files or not e.files[0].path:
        return
      file_info = e.files[0]
      try:
        with open(file_info.path, 'rb') as f:
          content = f.read()
        res = api_client.post(
            '/auth/upload-image/',
            params={'type': pending_upload['type']},
            files={'image': (file_info.name, content, file_info.content_type or 'image/jpeg')},
            timeout=15,
        )
        if res.status_code == 201:
          url = res.json().get('image_url', '')
          if pending_upload['type'] == 'avatar':
            profile_data['avatar_url'] = url
            notify(page, 'Profile photo updated!', '#16A34A', ft.icons.PERSON, title='Profile Photo')
          else:
            profile_data['banner_url'] = url
            notify(page, 'Banner updated!', '#16A34A', ft.icons.PHOTO_OUTLINED, title='Banner Photo')
          refresh_image_previews()
        else:
          detail = 'Upload failed. Make sure the profile-images bucket exists.'
          try:
            detail = res.json().get('detail', detail)
          except Exception:
            pass
          notify(page, detail, C.accent(), ft.icons.ERROR_OUTLINE, title='Upload Failed')
      except Exception as err:
        notify(page, f'Upload error: {err}', C.accent(), ft.icons.ERROR_OUTLINE, title='Upload Failed')

    file_picker = ft.FilePicker(on_result=upload_selected)
    existing_picker = _SHARED_FILE_PICKER[0]
    if existing_picker is not None:
      existing_picker.on_result = upload_selected
      file_picker = existing_picker
    else:
      _SHARED_FILE_PICKER[0] = file_picker
    if file_picker not in page.overlay:
      page.overlay.append(file_picker)
      page.update()

    def pick_avatar(e):
      pending_upload['type'] = 'avatar'
      file_picker.pick_files(allow_multiple=False, allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])

    def pick_banner(e):
      pending_upload['type'] = 'banner'
      file_picker.pick_files(allow_multiple=False, allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])

    username_field = ft.TextField(label='Username', value=profile_data['username'], border_color=C.accent(),
                                  text_size=13, height=44, bgcolor=C.field())
    fullname_field = ft.TextField(label='Full Name', value=profile_data['full_name'], border_color=C.input_border(),
                                  text_size=13, height=44, bgcolor=C.field())
    birthdate_field = ft.TextField(label='Date of Birth', value=profile_data['birth_date'], border_color=C.input_border(),
                                   hint_text='e.g. 1995-06-15', text_size=13, height=44, bgcolor=C.field())
    phone_field = ft.TextField(label='Phone Number', value=profile_data['phone'], border_color=C.input_border(),
                               hint_text='e.g. 0712345678', text_size=13, height=44, bgcolor=C.field())
    gender_drop = ft.Dropdown(label='Gender', value=profile_data['gender'] or None, border_color=C.input_border(),
                              text_size=13, bgcolor=C.field(),
                              options=[ft.dropdown.Option(g) for g in ['Male', 'Female', 'Other']])
    email_display = ft.Text(logged_in_email, size=12, color=C.soft())

    def save_profile(e):
      payload = {
          'username': (username_field.value or '').strip(),
          'full_name': (fullname_field.value or '').strip(),
          'birth_date': (birthdate_field.value or '').strip(),
          'gender': (gender_drop.value or '').strip(),
          'phone': (phone_field.value or '').strip(),
          'avatar_url': profile_data.get('avatar_url', ''),
          'banner_url': profile_data.get('banner_url', ''),
          'addresses': list(profile_data.get('addresses') or []),
      }
      try:
        res = api_client.patch(
            f'/auth/profile/{uid}',
            json=payload,
            timeout=10,
        )
        if res.status_code in [200, 201]:
          if payload.get('full_name'):
            user_info['name'] = payload['full_name']
          if payload.get('phone'):
            user_info['phone'] = payload['phone']
          hub_profile['avatar_url'] = payload.get('avatar_url', '')
          hub_profile['full_name'] = payload.get('full_name', '')
          hub_profile['username'] = payload.get('username', '')
          hub_profile['phone'] = payload.get('phone', '')
          notify(page, 'Profile saved!', '#16A34A', ft.icons.SAVE_OUTLINED, title='Profile Saved')
        else:
          detail = res.json().get('detail', 'Failed to save profile.') if res.content else 'Failed to save profile.'
          notify(page, detail, C.accent(), ft.icons.ERROR_OUTLINE, title='Save Failed')
      except Exception as err:
        notify(page, f'Save error: {err}', C.accent(), ft.icons.ERROR_OUTLINE, title='Save Failed')

    render_addresses()
    load_profile_async()

    return ft.Container(
        padding=0,
        bgcolor=C.bg(),
        expand=True,
        content=ft.Column([
            banner_preview,
            ft.Stack([
                ft.Container(
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(top=-40),
                    on_click=pick_avatar,
                    content=ft.Column([
                        ft.Stack([
                            avatar_preview,
                            ft.Container(
                                width=24,
                                height=24,
                                border_radius=12,
                                bgcolor=C.accent(),
                                alignment=ft.alignment.center,
                                left=-2,
                                bottom=-2,
                                tooltip='Change profile photo',
                                content=ft.Icon(ft.icons.CAMERA_ALT, size=13, color='white'),
                            ),
                        ]),
                        ft.Text(
                            'Tap to change photo',
                            size=10,
                            color=C.accent(),
                            weight=ft.FontWeight.W_500,
                        ),
                    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ),
            ]),
            ft.Row([
                ft.IconButton(ft.icons.ARROW_BACK, tooltip='Back to Hub', icon_color=C.text(),
                              on_click=lambda e: back_to_hub()),
                ft.Text('Edit Profile', size=20, weight=ft.FontWeight.BOLD, color=C.text()),
                ft.Container(width=48),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(
                padding=ft.padding.only(left=15, right=15, bottom=120),
                content=ft.Column([
                    ft.Container(
                        bgcolor=C.surface(), padding=15, border_radius=15, border=ft.border.all(1, C.divider()),
                        content=ft.Column([
                            ft.Row([ft.Icon(ft.icons.PHOTO_CAMERA_OUTLINED, color=C.accent(), size=18),
                                    ft.Text('Profile Photo', size=13, weight=ft.FontWeight.BOLD, color=C.text()),
                                    ft.Container(width=8),
                                    ft.OutlinedButton('Upload Photo', icon=ft.icons.UPLOAD_FILE, height=32,
                                                       on_click=pick_avatar)], spacing=4),
                            ft.Divider(color=C.divider(), height=16),
                            ft.Row([ft.Icon(ft.icons.PHOTO_OUTLINED, color=C.accent(), size=18),
                                    ft.Text('Banner Photo', size=13, weight=ft.FontWeight.BOLD, color=C.text()),
                                    ft.Container(width=8),
                                    ft.OutlinedButton('Upload Banner', icon=ft.icons.UPLOAD_FILE, height=32,
                                                       on_click=pick_banner)], spacing=4),
                        ], spacing=6),
                    ),
                    ft.Text('Account Email', size=11, color=C.soft()),
                    email_display,
                    ft.Divider(color=C.divider(), height=16),
                    username_field,
                    fullname_field,
                    birthdate_field,
                    phone_field,
                    gender_drop,
                    ft.Divider(color=C.divider(), height=16),
                    theme_drop,
                    ft.Divider(color=C.divider(), height=16),
                    ft.Text('Saved Addresses', size=13, weight=ft.FontWeight.BOLD, color=C.text()),
                    addresses_col,
                    ft.Row([
                        addresses_input,
                        ft.Container(
                            bgcolor=C.accent(), border_radius=10,
                            alignment=ft.alignment.center,
                            content=ft.IconButton(ft.icons.ADD, icon_color='white', tooltip='Save address', on_click=add_address),
                        ),
                    ], spacing=8, tight=True),
                    ft.Text('Used at checkout for delivery orders.', size=11, color=C.soft()),
                    ft.Container(height=6),
                    ft.ElevatedButton(
                        'Save Changes', width=380, height=46, bgcolor=C.accent(), color='white',
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
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
                  ft.Icon(ft.icons.FAVORITE_BORDER, size=56, color=C.muted()),
                  ft.Text('Your wishlist is empty.', size=14, color=C.soft()),
                  ft.Text('Tap the heart on any part to save it here.', size=12, color=C.muted()),
              ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
          )
      )
    else:
      for p_id, item in wishlist.items():
        img_url = str(item.get('image_url') or '') or \
            'https://raw.githubusercontent.com/wachiraericksonkinyua/ayutech/main/images/products/brakeparts/drum7l.png'
        wishlist_col.controls.append(
            ft.Container(
                bgcolor=C.surface(),
                border_radius=14,
                padding=10,
                border=ft.border.all(1, C.divider()),
                on_click=lambda e, it=item: open_wishlist_detail(it),
                content=ft.Row([
                    ft.Container(
                        width=52, height=52, border_radius=10, bgcolor=C.field(),
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Image(src=img_url, fit=ft.ImageFit.COVER, width=52, height=52),
                    ),
                    ft.Column([
                        ft.Text(item.get('name', 'Product'), size=12, weight=ft.FontWeight.BOLD,
                                color=C.text(), max_lines=1),
                        ft.Text(f"KES {float(item.get('price', 0)):,.0f}", size=12, color=C.accent(),
                                weight=ft.FontWeight.BOLD),
                    ], expand=True, spacing=2),
                    ft.IconButton(
                        ft.icons.FAVORITE, icon_color=C.accent(), icon_size=18, tooltip='Remove',
                        on_click=lambda e, it=item: remove_wishlist_item(it),
                    ),
                    ft.Icon(ft.icons.ARROW_FORWARD_IOS, size=14, color=C.muted()),
                ], spacing=10),
            )
        )

    def open_wishlist_detail(item):
      if open_detail_callback:
        open_detail_callback(item)
      else:
        show_top_notification(page, 'Opening product not supported on this view.', C.accent())

    def remove_wishlist_item(item):
      if item.get('id') in wishlist:
        del wishlist[item['id']]
      switch_tab_callback(4)

    return ft.Container(
        padding=ft.padding.only(left=15, right=15, top=15, bottom=120),
        bgcolor=C.bg(),
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.IconButton(ft.icons.ARROW_BACK, tooltip='Back to Hub', icon_color=C.text(),
                              on_click=lambda e: back_to_hub()),
                ft.Text('My Wishlist', size=20, weight=ft.FontWeight.BOLD, color=C.text()),
                ft.Container(width=48),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(f'{len(wishlist)} saved part' + ('s' if len(wishlist) != 1 else ''),
                    size=12, color=C.soft()),
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

  def open_track_page():
    global profile_page_mode
    profile_page_mode = 'track'
    switch_tab_callback(4)

  if profile_page_mode == 'settings':
    return build_settings_page()

  if profile_page_mode == 'wishlist':
    return build_wishlist_page()

  if profile_page_mode == 'track':
    return build_track_page(page, back_to_hub)

  # ---------------- MAIN HUB DASHBOARD ----------------
  logged_in_email = current_logged_in_user.get('email', 'Customer')

  hub_avatar_circle = ft.Container(
      width=56,
      height=56,
      border_radius=28,
      bgcolor=C.grad_primary(),
      alignment=ft.alignment.center,
      border=ft.border.all(2, 'white'),
      clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
      content=ft.Text(
          logged_in_email[:2].upper(),
          size=18,
          weight=ft.FontWeight.BOLD,
          color='white',
      ),
  )
  hub_name_text = ft.Text(
      logged_in_email.split('@')[0].capitalize(),
      size=16,
      weight=ft.FontWeight.BOLD,
      color='white',
  )

  def load_hub_profile():
    import threading

    def _apply():
      try:
        if hub_profile.get('avatar_url'):
          hub_avatar_circle.content = ft.Container(
              expand=True,
              border_radius=28,
              clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
              content=ft.Image(src=hub_profile['avatar_url'], fit=ft.ImageFit.COVER, width=56, height=56),
          )
        hub_name_text.value = (
            hub_profile.get('full_name')
            or (hub_profile.get('username') if hub_profile.get('username') != 'Customer' else '')
            or logged_in_email.split('@')[0].capitalize()
        )
        page.update()
      except Exception:
        pass

    def _load():
      try:
        uid = current_logged_in_user.get('id', '')
        if uid:
          pr = api_client.get(f'/auth/profile/{uid}')
          if pr.status_code == 200:
            data = pr.json()
            if isinstance(data, dict):
              hub_profile['avatar_url'] = data.get('avatar_url') or hub_profile.get('avatar_url', '')
              hub_profile['full_name'] = data.get('full_name') or hub_profile.get('full_name', '')
              hub_profile['username'] = data.get('username') or hub_profile.get('username', '')
              hub_profile['phone'] = data.get('phone') or hub_profile.get('phone', '')
        _apply()
      except Exception as e:
        print(f'Hub profile load error: {e}')

    threading.Thread(target=_load, daemon=True).start()

  profile_header = ft.Container(
      bgcolor=C.grad_deep(),
      border_radius=ft.border_radius.only(bottom_left=26, bottom_right=26),
      padding=20,
      shadow=C.card_shadow(),
      content=ft.Column([
          ft.Row([
              ft.Row([
                  ft.Icon(ft.icons.GARAGE_OUTLINED, color=C.accent(), size=18),
                  ft.Text(
                      'My Garage Hub',
                      size=15,
                      weight=ft.FontWeight.BOLD,
                      color='white',
                  ),
              ], spacing=6),
              ft.Row([
                  ft.Container(
                      padding=ft.padding.all(6),
                      border_radius=24,
                      bgcolor='#18FFFFFF',
                      on_click=lambda e: open_settings(),
                      content=ft.Icon(ft.icons.SETTINGS_OUTLINED, color='#B6AEA4', size=22),
                  ),
                  ft.IconButton(
                      icon=ft.icons.LOGOUT,
                      icon_color=C.accent(),
                      tooltip='Sign Out',
                      on_click=handle_logout,
                  ),
              ], spacing=6),
          ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
          ft.Container(
              on_click=lambda e: open_settings(),
              padding=ft.padding.symmetric(vertical=4),
              content=ft.Row([
                  hub_avatar_circle,
                  ft.Column([
                      hub_name_text,
                      ft.Text(logged_in_email, size=11, color='#B6AEA4'),
                  ], spacing=2),
                  ft.Icon(ft.icons.CHEVRON_RIGHT, size=16, color='#B6AEA4'),
              ], spacing=14),
          ),
          ft.Row([
              ft.Icon(ft.icons.KEYBOARD_ARROW_DOWN, size=12, color='#B6AEA4'),
              ft.Text('Tap your profile to edit photo & settings', size=10, color='#8F8780'),
          ], spacing=4),
      ], spacing=6),
  )

  def hub_tile(title, subtitle, icon, badge, on_click):
    return ft.Container(
        bgcolor=C.surface(),
        border_radius=16,
        padding=12,
        border=ft.border.all(1, C.divider()),
        shadow=C.soft_shadow(),
        on_click=on_click,
        content=ft.Row([
            ft.Row([
                ft.Container(
                    width=38,
                    height=38,
                    bgcolor=C.accent_soft(),
                    border_radius=12,
                    shadow=C.soft_shadow(),
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=C.accent(), size=19),
                ),
                ft.Column([
                    ft.Text(
                        title,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=C.text(),
                    ),
                    ft.Text(subtitle, size=11, color=C.soft()),
                ], spacing=2),
            ], spacing=12),
            ft.Row([
                ft.Container(
                    bgcolor=C.accent_soft(),
                    padding=ft.padding.symmetric(horizontal=9, vertical=4),
                    border_radius=20,
                    content=ft.Text(
                        badge,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=C.accent(),
                    ),
                )
                if badge
                else ft.Container(),
                ft.Icon(
                    ft.icons.ARROW_FORWARD_IOS, size=14, color=C.soft()
                ),
            ], spacing=6),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
    )

  nav_tiles = ft.Column([
      hub_tile(
          'Track My Order',
          'Check M-Pesa status by phone',
          ft.icons.LOCAL_SHIPPING_OUTLINED,
          'Live',
          lambda e: open_track_page(),
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
              bgcolor=C.surface(),
              border_radius=12,
              border=ft.border.all(1, C.divider()),
              content=ft.Text(
                  'No saved spare parts in your wishlist yet.',
                  size=12,
                  color=C.soft(),
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
              bgcolor=C.field(),
              border_radius=10,
              border=ft.border.all(1, C.divider()),
              on_click=lambda e, it=item: (open_detail_callback(it) if open_detail_callback else None),
              content=ft.Row([
                  ft.Container(
                      width=44, height=44, border_radius=8, bgcolor=C.surface_alt(),
                      clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                      content=ft.Image(src=img_url, fit=ft.ImageFit.COVER, width=44, height=44),
                  ),
                  ft.Column([
                      ft.Text(
                          item.get('name', 'Product'),
                          size=12,
                          weight=ft.FontWeight.BOLD,
                          color=C.text(),
                          max_lines=1,
                      ),
                      ft.Text(
                          f"KES {float(item.get('price', 0)):,.0f}",
                          size=11,
                          color=C.accent(),
                          weight=ft.FontWeight.BOLD,
                      ),
                  ], expand=True),
                  ft.IconButton(
                      icon=ft.icons.ADD_SHOPPING_CART,
                      icon_color=C.accent(),
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
  load_hub_profile()

  return ft.Container(
      padding=ft.padding.only(left=15, right=15, top=0, bottom=120),
      bgcolor=C.bg(),
      expand=True,
      content=ft.Column([
          profile_header,
          ft.Container(height=10),
          ft.Text(
              'Garage Dashboard',
              size=14,
              weight=ft.FontWeight.BOLD,
              color=C.text(),
          ),
          nav_tiles,
          ft.Divider(color=C.divider(), height=20),
          ft.Row([
              ft.Text(
                  'Saved Spares (Wishlist)',
                  size=14,
                  weight=ft.FontWeight.BOLD,
                  color=C.text(),
              ),
              ft.TextButton(
                  'View All',
                  style=ft.ButtonStyle(color=C.accent()),
                  on_click=lambda e: open_wishlist_page(),
              ),
          ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
          wishlist_container,
      ], scroll=ft.ScrollMode.AUTO, spacing=12),
  )