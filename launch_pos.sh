#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
cd "$HOME/ayutech-v2/backend" || exit 1
export PYTHONPATH=.
"/home/rome/ayutech-v2/backend/venv/bin/flet" run --module app.dashboard
