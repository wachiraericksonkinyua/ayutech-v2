# backend/main.py
# Flet entry point used only when packaging the customer client with
# `flet build` (see .github/workflows/build-app.yml).
#
# The desktop launcher (launch_customer.sh) keeps running
# app/ui/main_app.py directly, so this wrapper changes nothing at runtime.

import flet as ft

from app.ui.main_app import main

if __name__ == "__main__":
    ft.app(target=main)
