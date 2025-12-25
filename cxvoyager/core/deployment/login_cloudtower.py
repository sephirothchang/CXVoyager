# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudTower 登录辅助：模拟浏览器 GraphQL 登录以获取 token 与 cookie。"""
from __future__ import annotations

import logging
from typing import Dict

from cxvoyager.integrations.smartx.api_client import APIClient
from cxvoyager.core.deployment.runtime_context import RunContext


logger = logging.getLogger(__name__)


def _build_cookie_header(client: APIClient) -> str | None:
    jar = getattr(client, "session", None)
    if jar is None or not getattr(jar, "cookies", None):
        return None
    items = []
    for c in jar.cookies:  # type: ignore[attr-defined]
        items.append(f"{c.name}={c.value}")
    return "; ".join(items) if items else None


def login_cloudtower(ctx: RunContext, *, base_url: str, api_cfg: Dict[str, object], stage_logger) -> Dict[str, str | None]:
    """使用 GraphQL login 模拟浏览器登录，返回 token 与 cookie。"""

    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False

    username = "root"
    encoded_pwd = "NmQwNTQ2MTI4MDQxMjgzYTk3NDU3OGZmYjk3NmFhNGM6dm40by9nOE0xZ0ZjVmxBSmR2Nmk3QT09"

    stage_logger.debug(
        "CloudTower login debug params",
        progress_extra={"username": username, "encoded_pwd": encoded_pwd},
    )

    payload = {
        "operationName": "login",
        "variables": {
            "data": {
                "username": username,
                "password": encoded_pwd,
                "source": "LOCAL",
                "auth_config_id": None,
            }
        },
        "query": (
            "mutation login($data: LoginInput!) {\n  login(data: $data, effect: {encoded: true}) {\n    token\n    uid\n    need_mfa\n    mfa_meta {\n      recipient\n      mid\n      type\n      valid\n      __typename\n    }\n    __typename\n  }\n}\n"
        ),
    }

    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    try:
        resp = client.post("/api", payload)
    except Exception as exc:  # pragma: no cover - surfaced
        stage_logger.error("CloudTower 登录失败", progress_extra={"error": str(exc)})
        raise RuntimeError(f"CloudTower 登录失败: {exc}")

    token = None
    data = resp.get("data") if isinstance(resp, dict) else None
    login_data = data.get("login") if isinstance(data, dict) else None
    if isinstance(login_data, dict):
        token = login_data.get("token")

    cookie_header = _build_cookie_header(client)

    stage_logger.debug(
        "CloudTower login debug result",
        progress_extra={"cookie": cookie_header, "token": token},
    )

    stage_logger.info(
        "CloudTower 浏览器登录完成",
        progress_extra={"cookie_present": bool(cookie_header), "token_present": bool(token)},
    )

    if not cookie_header:
        raise RuntimeError("CloudTower 登录未返回有效 cookie（缺少 connect.sid）")

    return {"token": token, "cookie": cookie_header}
