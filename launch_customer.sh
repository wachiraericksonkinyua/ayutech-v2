#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
cd "$HOME/ayutech-v2/backend" || exit 1
source "$HOME/ayutech-v2/backend/venv/bin/activate"
export PYTHONPATH=.
python3 app/ui/main_app.py
