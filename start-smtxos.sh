#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_PORTABLE_DIR="$SCRIPT_DIR/smtxos-python"
PY_PORTABLE="$PY_PORTABLE_DIR/bin/python"
PY_PORTABLE_SRC_DIR="$SCRIPT_DIR/cxvoyager/resources/python-smtxos"
VENV_DIR="$SCRIPT_DIR/.venv-smtxos"
VENV_PYTHON="$VENV_DIR/bin/python"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
OFFLINE_DIR="$SCRIPT_DIR/cxvoyager/resources/offline_packages"
REQ_STAMP="$VENV_DIR/.requirements.sha256"
FONT_SRC="$SCRIPT_DIR/cxvoyager/resources/fonts/SourceHanSansSC-Normal.otf"
FONT_DST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"

ensure_locale() {
  # 控制台字体有限，使用英文消息避免乱码
  export LANG=en_US.UTF-8
  export LC_ALL=en_US.UTF-8
  export PYTHONIOENCODING=UTF-8
  export CXVOYAGER_LANG=en_US
}

install_font_if_needed() {
  if [ ! -f "$FONT_SRC" ]; then
    return
  fi

  mkdir -p "$FONT_DST_DIR"
  local dst_font="$FONT_DST_DIR/SourceHanSansSC-Normal.otf"

  if [ ! -f "$dst_font" ]; then
    cp "$FONT_SRC" "$dst_font"
    fc-cache -f "$FONT_DST_DIR" >/dev/null 2>&1 || true
    return
  fi

  # 如果已存在，同步更新为最新版
  if ! cmp -s "$FONT_SRC" "$dst_font"; then
    cp "$FONT_SRC" "$dst_font"
    fc-cache -f "$FONT_DST_DIR" >/dev/null 2>&1 || true
  fi
}

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

extract_portable_python() {
  if [ -x "$PY_PORTABLE" ]; then
    return
  fi

  if [ ! -d "$PY_PORTABLE_SRC_DIR" ]; then
    return
  fi

  local tarball=""
  for f in "$PY_PORTABLE_SRC_DIR"/*.tar.gz "$PY_PORTABLE_SRC_DIR"/*.tgz; do
    if [ -f "$f" ]; then
      tarball="$f"
      break
    fi
  done

  if [ -z "$tarball" ]; then
    return
  fi

  mkdir -p "$PY_PORTABLE_DIR"
  echo "解压内置 Python: $tarball -> $PY_PORTABLE_DIR"
  if tar -xzf "$tarball" -C "$PY_PORTABLE_DIR" --strip-components=1; then
    chmod +x "$PY_PORTABLE_DIR"/bin/* || true
  else
    echo "解压内置 Python 失败" >&2
  fi
}

main() {
  ensure_locale
  install_font_if_needed

  extract_portable_python

  PYTHON_BIN=""
  if [ -x "$PY_PORTABLE" ]; then
    PYTHON_BIN="$PY_PORTABLE"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  fi

  if [ -z "$PYTHON_BIN" ]; then
    echo "未找到可用的 python3，请先准备便携版 3.10+ 到 $PY_PORTABLE_DIR" >&2
    exit 1
  fi

  # 检查版本是否 >= 3.10，否则提醒使用便携版
  PY_VER_OUT="$($PYTHON_BIN - <<'PY'
import sys
v=sys.version_info
print(f"{v.major}.{v.minor}")
PY
  )"
  PY_MAJOR=${PY_VER_OUT%%.*}
  PY_MINOR=${PY_VER_OUT#*.}
  if [ "${PY_MAJOR:-0}" -lt 3 ] || { [ "${PY_MAJOR:-0}" -eq 3 ] && [ "${PY_MINOR:-0}" -lt 10 ]; }; then
    echo "当前 Python 版本 $PY_VER_OUT 低于 3.10，请放置或解压便携版到 $PY_PORTABLE_DIR" >&2
    exit 1
  fi

  if [ ! -x "$VENV_PYTHON" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  if [ -x "$VENV_PYTHON" ]; then
    # shellcheck disable=SC1091
    . "$VENV_DIR/bin/activate"
    install_requirements
    exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py" "$@"
  fi

  exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" "$@"
}

main "$@"
