# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudTower 虚拟网络查询辅助。"""
from __future__ import annotations

import logging
from typing import Dict, Any

from cxvoyager.library.integrations.smartx.api_client import APIClient
from cxvoyager.library.common.i18n import tr

logger = logging.getLogger(__name__)

GET_VLANS_ENDPOINT = "/v2/api/get-vlans"


def query_vnet_by_name(
    *,
    base_url: str,
    token: str,
    name: str,
    stage_logger,
    api_cfg: Dict[str, Any],
) -> str:
    """按名称查询虚拟网络（vnet），返回匹配到的 id。"""

    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    headers = {"Authorization": token}
    payload: Dict[str, Any] = {"where": {"name": name}}

    stage_logger.info(tr("deploy.query_vnet.start"), progress_extra={"name": name, "endpoint": GET_VLANS_ENDPOINT})
    resp = client.post(GET_VLANS_ENDPOINT, payload=payload, headers=headers)

    if isinstance(resp, list):
        matches = resp
    elif isinstance(resp, dict):
        matches = resp.get("data") or resp.get("vlans") or resp.get("items") or resp.get("result") or []
    else:
        matches = []

    if not isinstance(matches, list):
        raise RuntimeError("获取虚拟网络失败：响应格式异常")

    for item in matches:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip().lower() == name.strip().lower():
            vnet_id = item.get("id")
            if not vnet_id:
                break
            stage_logger.info(tr("deploy.query_vnet.found"), progress_extra={"id": vnet_id})
            return str(vnet_id)

    raise RuntimeError(f"未找到名称为 {name} 的虚拟网络")
