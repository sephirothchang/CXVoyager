#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-linux"
VENV_PYTHON="$VENV_DIR/bin/python"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

# Ensure virtualenv exists; create if missing
if [ ! -x "$VENV_PYTHON" ]; then
  python3 -m venv "$VENV_DIR"
fi

if [ -x "$VENV_PYTHON" ]; then
  # shellcheck disable=SC1091
  . "$VENV_DIR/bin/activate"
  if [ -f "$REQ_FILE" ]; then
    "$VENV_PYTHON" -m pip install --no-cache-dir -r "$REQ_FILE"
  fi
  exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py" "$@"
fi

# Fallback to system python3
exec python3 "$SCRIPT_DIR/main.py" "$@"
