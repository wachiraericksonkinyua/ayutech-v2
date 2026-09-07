#!/bin/bash
PROJECT_DIR="$HOME/ayutech-v2"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate

# Ensure backend server is running in the background
if ! pgrep -f "uvicorn app.main:app" > /dev/null; then
    uvicorn app.main:app --port 8000 --workers 4 > /tmp/ayutech_backend.log 2>&1 &
    sleep 2
fi

# Launch the Flet POS Dashboard
cd "$PROJECT_DIR/backend" || exit 1
PYTHONPATH=. flet run --module app.dashboard
