# app/ui/colors.py
# Theme-aware color helpers. Read the resolved brightness from app_state.is_dark,
# which theme.apply_theme() updates (covers system/light/dark modes).

import app.ui.state as app_state


def is_dark() -> bool:
    return bool(getattr(app_state, "is_dark", False))


# Main surfaces
def bg() -> str:
    return "#121212" if is_dark() else "#FFFFFF"


def surface() -> str:
    return "#1F2937" if is_dark() else "#F9FAFB"


def surface_alt() -> str:
    return "#374151" if is_dark() else "#F3F4F6"


def field() -> str:
    return "#1F2937" if is_dark() else "#FFFFFF"


def placeholder() -> str:
    return "#6B7280" if is_dark() else "#9CA3AF"


# Text colors
def text() -> str:
    return "#F3F4F6" if is_dark() else "#121212"


def body() -> str:
    return "#D1D5DB" if is_dark() else "#4B5563"


def muted() -> str:
    return "#9CA3AF"


def soft() -> str:
    return "#6B7280"


# Borders / dividers
def divider() -> str:
    return "#4B5563" if is_dark() else "#E5E7EB"


def input_border() -> str:
    return "#4B5563" if is_dark() else "#E5E7EB"


# Accents (constant brand colors)
def accent() -> str:
    return "#DC2626"


def accent_soft() -> str:
    return "#7F1D1D" if is_dark() else "#FEE2E2"


def success() -> str:
    return "#25D366"


def danger() -> str:
    return "#DC2626"