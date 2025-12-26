# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudTower login helper.

This module provides a single-purpose function to obtain a fresh CloudTower
session token via the login API. It keeps dependencies minimal so other modules
can import and reuse it without pulling handler-specific logic.
"""
from __future__ import annotations

import logging
from typing import Optional

from cxvoyager.library.integrations.smartx.api_client import APIClient

DEFAULT_LOGIN_ENDPOINT = "/v2/api/login"
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "HC!r0cks"
logger = logging.getLogger(__name__)


def cloudtower_login(
    *,
    client: APIClient,
    ip: str,
    username: str = DEFAULT_USERNAME,
    password: str = DEFAULT_PASSWORD,
    endpoint: str = DEFAULT_LOGIN_ENDPOINT,
    logger_adapter: Optional[logging.LoggerAdapter] = None,
) -> str:
    """Perform CloudTower login and return the session token.

    Parameters
    ----------
    client: APIClient
        HTTP client instance; caller controls verify/timeout/mock.
    ip: str
        CloudTower management IP (used only for log context).
    username, password: str
        Credentials to authenticate; defaults match installation defaults.
    endpoint: str
        Login API path. Defaults to "/v2/api/login".
    logger_adapter: LoggerAdapter, optional
        If provided, used for stage-aware logging; falls back to module logger.

    Raises
    ------
    RuntimeError
        If no token is returned by the login API.
    """

    payload = {"username": username, "source": "LOCAL", "password": password}
    log = logger_adapter or logger
    log.debug("Calling CloudTower login", extra={"ip": ip, "endpoint": endpoint, "user": username})

    response = client.post(endpoint, payload=payload, headers={"content-type": "application/json"})

    cloudtower_token: Optional[str] = None
    if isinstance(response, dict):
        data = response.get("data") if isinstance(response.get("data"), dict) else None
        if isinstance(data, dict) and data.get("token"):
            cloudtower_token = str(data.get("token"))
        elif response.get("token"):
            cloudtower_token = str(response.get("token"))

    if not cloudtower_token:
        raise RuntimeError("CloudTower 登录未返回 token")

    log.info("CloudTower 登录成功并获取 token", extra={"ip": ip, "has_token": True})
    return cloudtower_token
