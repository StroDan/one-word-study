#!/bin/sh
# One command to run the app: creates .venv with Python 3.12 if needed, installs deps, starts Flask.
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3.12
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
echo "Open http://127.0.0.1:5050 in your browser (Ctrl+C to stop)."
exec .venv/bin/python app.py
