# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal i18n helper for bilingual (en/zh) messages.

读取 `cxvoyager/langs` 下的语言文件（优先 YAML，退化为简单缩进解析），
通过 `tr(key, lang=None, **kwargs)` 获取格式化后的文案。缺少 key 时回退英文，
仍缺失则返回原始 key，避免日志崩溃。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict


LANG_DIR = Path(__file__).resolve().parents[1] / "langs"
DEFAULT_LANG = "zh"

_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_yaml_like(path: Path) -> Dict[str, Any]:
    """Load a very small subset of YAML (key-value with indentation)."""

    def normalize_value(val: str) -> Any:
        val = val.strip()
        if val.startswith("\"") and val.endswith("\""):
            return val[1:-1]
        if val.startswith("'") and val.endswith("'"):
            return val[1:-1]
        return val

    root: Dict[str, Any] = {}
    stack: list[tuple[int, Dict[str, Any]]] = [(0, root)]

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, _, rest = line.lstrip().partition(":")
        key = key.strip()
        value = rest.strip()

        while stack and indent < stack[-1][0]:
            stack.pop()
        current = stack[-1][1]

        if not value:
            node: Dict[str, Any] = {}
            current[key] = node
            stack.append((indent + 2, node))
        else:
            current[key] = normalize_value(value)

    return root


def _load_lang(lang: str) -> Dict[str, Any]:
    if lang in _CACHE:
        return _CACHE[lang]

    path = LANG_DIR / f"{lang}.yml"
    if not path.exists():
        _CACHE[lang] = {}
        return _CACHE[lang]

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data = _load_yaml_like(path)

    _CACHE[lang] = data if isinstance(data, dict) else {}
    return _CACHE[lang]


def _normalize_lang_code(raw: str | None) -> str:
    if not raw:
        return DEFAULT_LANG
    code = raw.strip().lower().replace("-", "_")
    if code.startswith("zh"):
        return "zh"
    if code.startswith("en"):
        return "en"
    base = code.split("_")[0]
    return base or DEFAULT_LANG


def get_current_lang() -> str:
    env_lang = os.environ.get("CXVOYAGER_LANG") or os.environ.get("LANG") or os.environ.get("LC_ALL")
    return _normalize_lang_code(env_lang)


def _lookup(data: Dict[str, Any], key: str) -> Any:
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node.get(part)
    return node


def tr(key: str, lang: str | None = None, **kwargs) -> str:
    """Translate a key with formatting. Fallback: lang->en->key itself."""

    lang_code = _normalize_lang_code(lang)
    data_lang = _load_lang(lang_code)
    data_en = _load_lang("en")

    message = _lookup(data_lang, key) or _lookup(data_en, key) or key

    try:
        if kwargs:
            return str(message).format(**kwargs)
        return str(message)
    except Exception:
        return str(message)