import subprocess
import sys
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


def _system_is_dark() -> bool:
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            return "Dark" in out
        if sys.platform == "linux":
            out = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            if "dark" in out:
                return True
            out2 = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            return "dark" in out2.lower()
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        return False
    except Exception:
        return False


def apply_theme(page, mode=None):
    mode = mode or app_state.theme_mode
    app_state.theme_mode = mode
    resolved_dark = mode == "dark" or (mode == "system" and _system_is_dark())
    app_state.is_dark = resolved_dark
    page.theme_mode = THEME_MODES.get(mode, ft.ThemeMode.SYSTEM)
    page.bgcolor = "#121212" if resolved_dark else "#FFFFFF"
    try:
        page.client_storage.set("ayutech_theme", mode)
    except Exception:
        pass
    for fn in _theme_listeners:
        try:
            fn("dark" if resolved_dark else "light")
        except Exception:
            pass
    page.update()


def load_theme(page):
    try:
        saved = page.client_storage.get("ayutech_theme")
        if not saved:
            apply_theme(page, "system")
        elif saved in THEME_MODES:
            apply_theme(page, saved)
        else:
            apply_theme(page, "system")
    except Exception:
        try:
            apply_theme(page, "system")
        except Exception:
            pass