import flet as ft
import app.ui.state as app_state

THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}

_theme_listeners = []


def set_theme_listener(fn):
    if fn not in _theme_listeners:
        _theme_listeners.append(fn)


def apply_theme(page, mode=None):
    mode = mode or app_state.theme_mode
    app_state.theme_mode = mode
    page.theme_mode = THEME_MODES.get(mode, ft.ThemeMode.SYSTEM)
    page.bgcolor = "#121212" if page.theme_mode == ft.ThemeMode.DARK else "#FFFFFF"
    try:
        page.client_storage.set("ayutech_theme", mode)
    except Exception:
        pass
    for fn in _theme_listeners:
        try:
            fn(mode)
        except Exception:
            pass
    page.update()


def load_theme(page):
    try:
        saved = page.client_storage.get("ayutech_theme")
        if saved in THEME_MODES:
            apply_theme(page, saved)
    except Exception:
        pass