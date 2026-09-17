# app/ui/colors.py
# AyuTech design system - warm charcoal + vermillion, theme-aware (light / dark).
# Read the resolved brightness from app_state.is_dark (set by theme.apply_theme()).

import flet as ft
import app.ui.state as app_state


def is_dark() -> bool:
    return bool(getattr(app_state, "is_dark", False))


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------
def bg() -> str:
    return "#0F0D0C" if is_dark() else "#F6F4F1"


def surface() -> str:
    return "#181615" if is_dark() else "#FFFFFF"


def surface_raised() -> str:
    return "#211E1C" if is_dark() else "#FFFFFF"


def surface_alt() -> str:
    return "#26221F" if is_dark() else "#EFECE7"


def field() -> str:
    return "#1A1715" if is_dark() else "#FFFFFF"


def divider() -> str:
    return "#2E2A27" if is_dark() else "#E8E4DE"


def input_border() -> str:
    return "#3A352F" if is_dark() else "#D8D3CB"


def placeholder() -> str:
    return "#6F6860" if is_dark() else "#A39B90"


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def text() -> str:
    return "#F4F2EF" if is_dark() else "#1B1714"


def body() -> str:
    return "#B6AEA4" if is_dark() else "#4A433B"


def muted() -> str:
    return "#857D74"


def soft() -> str:
    return "#6D665E"


# ---------------------------------------------------------------------------
# Brand accents
# ---------------------------------------------------------------------------
def accent() -> str:
    return "#EF4650" if is_dark() else "#C41E2E"


def accent_deep() -> str:
    return "#B01828" if is_dark() else "#8F1220"


def accent_soft() -> str:
    return "#331A1C" if is_dark() else "#FBE4E1"


def on_accent() -> str:
    return "#FFFFFF"


def success() -> str:
    return "#28CE7C" if is_dark() else "#0FA35C"


def success_soft() -> str:
    return "#143024" if is_dark() else "#E3F6EC"


def info() -> str:
    return "#5BA7F5" if is_dark() else "#1E5FBF"


def info_soft() -> str:
    return "#152940" if is_dark() else "#E4EEFB"


def warn() -> str:
    return "#F59E0B"


def warn_soft() -> str:
    return "#33270F" if is_dark() else "#FDF1DC"


def danger() -> str:
    return accent()


# ---------------------------------------------------------------------------
# Gradients & shadows
# ---------------------------------------------------------------------------
def grad_primary():
    """Vermillion brand gradient for CTAs, banners and headers."""
    return ft.LinearGradient(
        begin=ft.alignment.top_center,
        end=ft.alignment.bottom_center,
        colors=["#E8444F", "#B11728"],
    )


def grad_deep():
    """Deep charcoal brand gradient for premium headers (hub / settings)."""
    return ft.LinearGradient(
        begin=ft.alignment.top_center,
        end=ft.alignment.bottom_center,
        colors=["#191512", "#0B0908"],
    )


def grad_success():
    return ft.LinearGradient(
        begin=ft.alignment.top_center,
        end=ft.alignment.bottom_center,
        colors=["#34D682", "#0F9D58"],
    )


def card_shadow():
    return ft.BoxShadow(blur_radius=18, spread_radius=-6, color="#1A000000")


def soft_shadow():
    return ft.BoxShadow(blur_radius=12, spread_radius=-4, color="#14000000")