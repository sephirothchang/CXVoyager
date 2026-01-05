#!/usr/bin/env bash
set -euo pipefail

echo "启动 CXVoyager 启动脚本 (macOS)..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
OFFLINE_DIR="$SCRIPT_DIR/cxvoyager/common/resources/offline_packages"
REQ_STAMP="$VENV_DIR/.requirements.sha256"
REQUIRED_PY_VERSION="3.11.9"
PYTHON_INSTALLER="$SCRIPT_DIR/cxvoyager/common/resources/python-macos/python-3.11.9-macos11.pkg"
PYTHON_CMD="python3"

ensure_python() {
  local detected=""
  if command -v "$PYTHON_CMD" >/dev/null 2>&1; then
    detected=$($PYTHON_CMD -V 2>&1 | awk '{print $2}')
  fi

  if [ "$detected" != "$REQUIRED_PY_VERSION" ]; then
    printf '检测到系统 Python (%s) 不符合要求，是否安装内置 %s? [Y/N]: ' "$detected" "$REQUIRED_PY_VERSION"
    read -r reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
      if [ ! -f "$PYTHON_INSTALLER" ]; then
        echo "找不到 Python 安装包: $PYTHON_INSTALLER" >&2
        exit 1
      fi
      echo "正在安装 $REQUIRED_PY_VERSION ..."
      sudo installer -pkg "$PYTHON_INSTALLER" -target / >/dev/null
      PYTHON_CMD="/usr/local/bin/python3"
    else
      echo "使用系统 Python: ${detected:-unknown}"
    fi
  fi
}

ensure_python
CHOSEN_PY_VERSION=$($PYTHON_CMD -V 2>&1 | awk '{print $2}')
echo "使用 Python ${CHOSEN_PY_VERSION:-unknown} ($PYTHON_CMD)"

# Prepare offline packages if requirements changed
OFFLINE_STAMP="$SCRIPT_DIR/.offline_packages.sha256"
if [ ! -f "$OFFLINE_STAMP" ] || [ "$(cat "$OFFLINE_STAMP")" != "$(shasum -a 256 "$REQ_FILE" | awk '{print $1}')" ]; then
  echo "准备离线安装包..."
  "$PYTHON_CMD" "$SCRIPT_DIR/scripts/prepare_offline_installation_packages.py"
  shasum -a 256 "$REQ_FILE" | awk '{print $1}' > "$OFFLINE_STAMP"
fi

install_requirements() {
  if [ ! -f "$REQ_FILE" ]; then
    return
  fi

  local cur_hash
  cur_hash=$(shasum -a 256 "$REQ_FILE" | awk '{print $1}')

  if [ -f "$REQ_STAMP" ]; then
    local saved_hash
    saved_hash=$(cat "$REQ_STAMP")
    if [ "$saved_hash" = "$cur_hash" ]; then
      echo "依赖未变化，跳过安装"
      return
    fi
  fi

  if [ -d "$OFFLINE_DIR" ] && compgen -G "$OFFLINE_DIR/*" > /dev/null; then
    echo "使用离线包安装依赖..."
    if "$VENV_PYTHON" -m pip install --no-index --find-links="$OFFLINE_DIR" -r "$REQ_FILE"; then
      echo "$cur_hash" > "$REQ_STAMP"
      return
    fi
    echo "离线依赖安装失败，尝试联网安装..." >&2
  else
    echo "未找到离线依赖，尝试联网安装..." >&2
    echo "使用联网安装依赖..."
  fi

  "$VENV_PYTHON" -m pip install --no-cache-dir -r "$REQ_FILE"
  echo "$cur_hash" > "$REQ_STAMP"
}

    echo "创建虚拟环境..."
# Ensure virtualenv exists; create if missing
if [ ! -x "$VENV_PYTHON" ]; then
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

if [ -x "$VENV_PYTHON" ]; then
  . "$VENV_DIR/bin/activate"
  install_requirements
  exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py" "$@"
fi

# Fallback to system python
exec "$PYTHON_CMD" "$SCRIPT_DIR/main.py" "$@"
