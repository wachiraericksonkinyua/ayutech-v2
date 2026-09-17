import subprocess
import sys
import flet as ft
import app.ui.state as app_state

THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}

# Explicit, high-contrast schemes so native controls (inputs, dialogs, menus)
# stay readable in both modes instead of relying on Flet defaults.
_LIGHT_SCHEME = dict(
    primary="#C41E2E",
    on_primary="#FFFFFF",
    primary_container="#FBE4E1",
    on_primary_container="#5C0A13",
    secondary="#8F1220",
    on_secondary="#FFFFFF",
    surface="#FFFFFF",
    on_surface="#1B1714",
    surface_variant="#EFECE7",
    on_surface_variant="#4A433B",
    background="#F6F4F1",
    on_background="#1B1714",
    outline="#D8D3CB",
    outline_variant="#E8E4DE",
    error="#B3261E",
    on_error="#FFFFFF",
    shadow="#000000",
    scrim="#000000",
)

_DARK_SCHEME = dict(
    primary="#EF4650",
    on_primary="#FFFFFF",
    primary_container="#331A1C",
    on_primary_container="#FBE4E1",
    secondary="#EF4650",
    on_secondary="#FFFFFF",
    surface="#181615",
    on_surface="#F4F2EF",
    surface_variant="#26221F",
    on_surface_variant="#B6AEA4",
    background="#0F0D0C",
    on_background="#F4F2EF",
    outline="#3A352F",
    outline_variant="#2E2A27",
    error="#F2B8B5",
    on_error="#601410",
    shadow="#000000",
    scrim="#000000",
)

_theme_listeners = []


def configure_themes(page):
    """Attach explicit light/dark themes to the page (called once at startup)."""
    try:
        page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(**_LIGHT_SCHEME), use_material3=True
        )
        page.dark_theme = ft.Theme(
            color_scheme=ft.ColorScheme(**_DARK_SCHEME), use_material3=True
        )
    except Exception as err:
        print(f"Theme configuration warning: {err}")


def toggle_theme(page) -> str:
    """Flip between light and dark and return the newly applied mode."""
    new_mode = "light" if app_state.is_dark else "dark"
    apply_theme(page, new_mode)
    return new_mode


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
    page.bgcolor = "#0F0D0C" if resolved_dark else "#F6F4F1"
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