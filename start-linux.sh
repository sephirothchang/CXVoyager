#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-linux"
VENV_PYTHON="$VENV_DIR/bin/python"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
OFFLINE_DIR="$SCRIPT_DIR/cxvoyager/common/resources/offline_packages"
REQ_STAMP="$VENV_DIR/.requirements.sha256"

install_requirements() {
  if [ ! -f "$REQ_FILE" ]; then
    return
  fi

  local cur_hash
  cur_hash=$(sha256sum "$REQ_FILE" | awk '{print $1}')

  if [ -f "$REQ_STAMP" ]; then
    local saved_hash
    saved_hash=$(cat "$REQ_STAMP")
    if [ "$saved_hash" = "$cur_hash" ]; then
      return
    fi
  fi

  if [ -d "$OFFLINE_DIR" ] && compgen -G "$OFFLINE_DIR/*" > /dev/null; then
    if "$VENV_PYTHON" -m pip install --no-index --find-links="$OFFLINE_DIR" -r "$REQ_FILE"; then
      echo "$cur_hash" > "$REQ_STAMP"
      return
    fi
    echo "离线依赖安装失败，尝试联网安装..." >&2
  else
    echo "未找到离线依赖，尝试联网安装..." >&2
  fi

  "$VENV_PYTHON" -m pip install --no-cache-dir -r "$REQ_FILE"
  echo "$cur_hash" > "$REQ_STAMP"
}

# Ensure virtualenv exists; create if missing
if [ ! -x "$VENV_PYTHON" ]; then
  python3 -m venv "$VENV_DIR"
fi

if [ -x "$VENV_PYTHON" ]; then
  # shellcheck disable=SC1091
  . "$VENV_DIR/bin/activate"
  install_requirements
  exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py" "$@"
fi

# Fallback to system python3
exec python3 "$SCRIPT_DIR/main.py" "$@"
