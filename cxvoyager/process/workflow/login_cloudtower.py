# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudTower 登录辅助：模拟浏览器 GraphQL 登录以获取 token 与 cookie。"""
from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse
from typing import Dict

from cxvoyager.library.integrations.smartx.api_client import APIClient
from cxvoyager.process.workflow.runtime_context import RunContext
from cxvoyager.library.common.i18n import tr


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

    timeout = 10
    if isinstance(api_cfg, dict):
        raw = api_cfg.get("timeout", 10)
        if isinstance(raw, (int, str)):
            timeout = int(raw)

    verify_ssl: bool | str = False
    if isinstance(api_cfg, dict):
        raw_verify = api_cfg.get("verify_ssl", False)
        if isinstance(raw_verify, (bool, str)):
            verify_ssl = raw_verify

    username = "root"
    # 默认密码为示例值；优先从解析后的规划表中读取 CloudTower root 密码
    password = "HC!r0cks"
    plan = getattr(ctx, "plan", None)
    mgmt = getattr(plan, "mgmt", None)
    if mgmt and getattr(mgmt, "root密码", None):
        password = str(getattr(mgmt, "root密码"))
    else:
        parsed_plan = ctx.extra.get("parsed_plan") if isinstance(ctx.extra, dict) else None
        if isinstance(parsed_plan, dict):
            mgmt_section = parsed_plan.get("mgmt", {}) if isinstance(parsed_plan, dict) else {}
            records = mgmt_section.get("records") if isinstance(mgmt_section, dict) else None
            if isinstance(records, list) and records:
                record = records[0] or {}
                pwd_candidate = record.get("root密码") or record.get("cloudtower_root_password")
                if pwd_candidate:
                    password = str(pwd_candidate)

    stage_logger.debug(
        tr("deploy.cloudtower_login.debug_params"),
        progress_extra={"username": username, "encoded_pwd": password},
    )

    payload = {
        "operationName": "login",
        "variables": {
            "data": {
                "username": username,
                "password": password,
                "source": "LOCAL",
                "auth_config_id": None,
            }
        },
        "query": (
            "mutation login($data: LoginInput!) {\n  login(data: $data, effect: {encoded: true}) {\n    token\n    uid\n    need_mfa\n    mfa_meta {\n      recipient\n      mid\n      type\n      valid\n      __typename\n    }\n    __typename\n  }\n}\n"
        ),
    }

    # 规范 base_url：若缺少 scheme 或为 http，则强制使用 https，避免中途被重定向导致 POST 变为 GET
    try:
        parsed = urlparse(str(base_url))
        scheme = parsed.scheme.lower() if parsed.scheme else ""
        if scheme != "https":
            # 替换 scheme 或补全为 https
            parsed = parsed._replace(scheme="https")
            # 当原始没有 netloc（例如直接传入 IP），urlparse 会把 IP 放在 path，需要处理
            if not parsed.netloc and parsed.path:
                # 把 path 视为 netloc
                parsed = parsed._replace(netloc=parsed.path, path="")
        base_url = urlunparse(parsed)
    except Exception:
        # 保守回退：若解析出错，确保以 https:// 前缀
        if not str(base_url).lower().startswith("https://"):
            base_url = f"https://{base_url.lstrip('http://').lstrip('https://')}"

    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    try:
        resp = client.post("/api", payload)
    except Exception as exc:  # pragma: no cover - surfaced
        stage_logger.error(tr("deploy.cloudtower_login.login_failed"), progress_extra={"error": str(exc)})
        raise RuntimeError(f"CloudTower 登录失败: {exc}")

    token = None
    data = resp.get("data") if isinstance(resp, dict) else None
    login_data = data.get("login") if isinstance(data, dict) else None
    if isinstance(login_data, dict):
        token = login_data.get("token")

    cookie_header = _build_cookie_header(client)

    stage_logger.debug(
        tr("deploy.cloudtower_login.debug_result"),
        progress_extra={"cookie": cookie_header, "token": token},
    )

    stage_logger.info(
        tr("deploy.cloudtower_login.login_complete"),
        progress_extra={"cookie_present": bool(cookie_header), "token_present": bool(token)},
    )

    if not cookie_header:
        raise RuntimeError("CloudTower 登录未返回有效 cookie（缺少 connect.sid）")

    return {"token": token, "cookie": cookie_header}
