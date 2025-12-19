# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.
#
# CXVoyager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CXVoyager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CXVoyager.  If not, see <https://www.gnu.org/licenses/>.

"""配置加载模块。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import os
import yaml

from ..system_constants import DEFAULT_CONFIG_FILE


DEFAULT_SMARTX_TOKEN = "e79b85fc18b7402fbcc0391fe8d7d24c"
DEFAULT_PREINIT_TOKEN_KEY = "default-x-smartx-token"


class Config(dict):
    """配置对象，dict子类，支持点式访问（简单实现）。"""

    def __getattr__(self, item):  # noqa: D401
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def load_config(path: Path | None = None) -> Config:
    """加载YAML配置，返回Config对象。"""

    cfg_path = path or DEFAULT_CONFIG_FILE
    data: Dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

    data = _normalize_api_token(data)

    env_overrides = _load_env_overrides()
    if env_overrides:
        data = _deep_merge_dicts(data, env_overrides)

    data = _normalize_api_token(data)

    return Config(data)


def _load_env_overrides() -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}

    def _pick_env(*keys: str) -> str | None:
        for key in keys:
            value = os.getenv(key)
            if value:
                return value.strip()
        return None

    token = _pick_env("CXVOYAGER_API_TOKEN", "SMARTX_TOKEN", "X_SMARTX_TOKEN")
    if token:
        overrides.setdefault("api", {})["x-smartx-token"] = token
        overrides.setdefault("api", {})[DEFAULT_PREINIT_TOKEN_KEY] = token

    base_url = _pick_env("CXVOYAGER_API_BASE_URL", "SMARTX_API_BASE_URL")
    if base_url:
        overrides.setdefault("api", {})["base_url"] = base_url

    timeout_raw = _pick_env("CXVOYAGER_API_TIMEOUT", "SMARTX_API_TIMEOUT")
    if timeout_raw:
        try:
            overrides.setdefault("api", {})["timeout"] = int(timeout_raw)
        except ValueError:
            pass

    mock = _pick_env("CXVOYAGER_API_MOCK", "SMARTX_API_MOCK")
    if mock is not None:
        value = mock.lower()
        overrides.setdefault("api", {})["mock"] = value in {"1", "true", "yes", "on"}

    return overrides


def _deep_merge_dicts(original: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(original)
    for key, value in updates.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_api_token(data: Dict[str, Any] | None) -> Dict[str, Any]:
    base = data or {}
    result = dict(base)
    api_cfg = dict(result.get("api", {}) or {})

    token_value = api_cfg.get("x-smartx-token")
    if not token_value:
        legacy = api_cfg.get("token")
        token_value = legacy or DEFAULT_SMARTX_TOKEN

    api_cfg["x-smartx-token"] = token_value
    api_cfg.setdefault(DEFAULT_PREINIT_TOKEN_KEY, DEFAULT_SMARTX_TOKEN)
    api_cfg.pop("token", None)

    result["api"] = api_cfg
    return result

