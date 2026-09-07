#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
cd "$HOME/ayutech-v2/backend" || exit 1

# Activate virtual environment
source "$HOME/ayutech-v2/backend/venv/bin/activate"

# Launch Python target directly (bypasses flet CLI watcher hang)
export PYTHONPATH=.
python3 -m app.dashboard
