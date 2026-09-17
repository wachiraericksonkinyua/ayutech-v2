# app/ui/notifications.py

import threading
import time as _time
import flet as ft
import app.ui.state as app_state

_active_toasts = []


def notify(page: ft.Page, message: str, color: str = "#121212", icon: str = None,
           title: str = None, duration: float = 2.6):
    """Record a notification in the center and show a top toast."""
    try:
        app_state.notifications.insert(0, {
            "id": _time.time_ns(),
            "title": title or "AyuTech",
            "message": message,
            "color": color,
            "icon": icon or ft.icons.CIRCLE_OUTLINED,
            "time": _time.strftime("%H:%M"),
        })
        if len(app_state.notifications) > 50:
            app_state.notifications = app_state.notifications[:50]
    except Exception:
        pass
    show_top_notification(page, message, color, icon, title, duration)


def show_top_notification(page: ft.Page, message: str, color: str = "#121212", icon: str = None,
                          title: str = None, duration: float = 2.6):
    """Show a compact toast below the top header, stacking cleanly on the right side."""
    TOP_START = 62
    TOAST_HEIGHT = 54
    GAP = 8
    WIDTH = 296

    if len(_active_toasts) >= 4:
        return

    if title:
        toast_content = ft.Row([
            ft.Icon(icon or ft.icons.CHECK_CIRCLE_OUTLINE, color="white", size=16),
            ft.Column([
                ft.Text(title, color="white", size=11, weight=ft.FontWeight.BOLD),
                ft.Text(message, color="white", size=11,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=0, tight=True, expand=True),
        ], spacing=8, tight=True)
    else:
        toast_content = ft.Row([
            ft.Icon(icon or ft.icons.CHECK_CIRCLE_OUTLINE, color="white", size=16),
            ft.Text(message, color="white", size=11,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
        ], spacing=8, tight=True)

    toast = ft.Container(
        right=12,
        top=TOP_START + len(_active_toasts) * (TOAST_HEIGHT + GAP),
        width=WIDTH,
        height=TOAST_HEIGHT,
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor=color,
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=14, color="#40000000"),
        content=toast_content,
    )

    def _relayout():
        for i, (other, _) in enumerate(_active_toasts):
            other.top = TOP_START + i * (TOAST_HEIGHT + GAP)

    def close():
        try:
            if toast in page.overlay:
                page.overlay.remove(toast)
            _active_toasts[:] = [t for t, _ in _active_toasts if t is not toast]
            _relayout()
            page.update()
        except Exception:
            pass

    toast.on_click = lambda e: close()

    try:
        page.overlay.append(toast)
        _active_toasts.append((toast, None))
        page.update()
    except Exception as e:
        print(f"Notification error: {e}")
        return

    def dismiss():
        try:
            threading.Event().wait(duration)
            close()
        except Exception:
            pass

    threading.Thread(target=dismiss, daemon=True).start()