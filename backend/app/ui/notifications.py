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
    """Show a slim notification toast pinned to the top of the window, stacking under any active toasts."""
    if title:
        toast_content = ft.Row([
            ft.Icon(icon or ft.icons.CHECK_CIRCLE_OUTLINE, color="white", size=16),
            ft.Column([
                ft.Text(title, color="white", size=11, weight=ft.FontWeight.BOLD),
                ft.Text(message, color="white", size=12, weight=ft.FontWeight.BOLD,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=0, tight=True),
        ], spacing=8, tight=True)
    else:
        toast_content = ft.Row([
            ft.Icon(icon or ft.icons.CHECK_CIRCLE_OUTLINE, color="white", size=16),
            ft.Text(message, color="white", size=12, weight=ft.FontWeight.BOLD,
                    max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=8, tight=True)

    toast = ft.Container(
        left=15,
        right=15,
        top=14 + len(_active_toasts) * 64,
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
        bgcolor=color,
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=14, color="#40000000"),
        content=toast_content,
    )

    def _relayout():
        for i, (other, _) in enumerate(_active_toasts):
            other.top = 14 + i * 64

    def close():
        try:
            if toast in page.overlay:
                page.overlay.remove(toast)
            if toast in [t for t, _ in _active_toasts]:
                _active_toasts[:] = [t for t, _ in _active_toasts if t is not toast]
                _relayout()
                page.update()
        except Exception:
            pass

    try:
        page.overlay.append(toast)
        _active_toasts.append((toast, None))
        page.update()
    except Exception as e:
        print(f"Notification error: {e}")
        return

    def dismiss():
        threading.Event().wait(duration)
        close()

    threading.Thread(target=dismiss, daemon=True).start()