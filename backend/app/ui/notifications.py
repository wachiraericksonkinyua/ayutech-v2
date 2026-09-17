# app/ui/notifications.py

import threading
import flet as ft


def show_top_notification(page: ft.Page, message: str, color: str = "#121212", icon: str = None, duration: float = 2.6):
    """Show a slim notification toast pinned to the top of the window."""
    toast = ft.Container(
        left=15,
        right=15,
        top=14,
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
        bgcolor=color,
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=14, color="#40000000"),
        content=ft.Row([
            ft.Icon(icon or ft.icons.CHECK_CIRCLE_OUTLINE, color="white", size=16),
            ft.Text(message, color="white", size=12, weight=ft.FontWeight.BOLD, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=8, tight=True),
    )
    try:
        page.overlay.append(toast)
        page.update()
    except Exception as e:
        print(f"Notification error: {e}")
        return

    def dismiss():
        threading.Event().wait(duration)
        try:
            if toast in page.overlay:
                page.overlay.remove(toast)
                page.update()
        except Exception:
            pass

    threading.Thread(target=dismiss, daemon=True).start()