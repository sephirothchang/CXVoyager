# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudTower 集群查询公用模块：按名称查询并缓存结果。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from cxvoyager.core.deployment.handlers.deploy_cloudtower import CLOUDTOWER_GET_CLUSTERS_ENDPOINT
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.integrations.smartx.api_client import APIClient
from cxvoyager.common.i18n import tr

logger = logging.getLogger(__name__)


def _extract_clusters(response: Any) -> List[Dict[str, Any]]:
    clusters: List[Dict[str, Any]] = []
    if isinstance(response, list):
        for item in response:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if isinstance(data, dict) and isinstance(data.get("clusters"), list):
                clusters.extend([c for c in data.get("clusters", []) if isinstance(c, dict)])
            else:
                clusters.append(item)
    elif isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, list):
            clusters.extend([c for c in data if isinstance(c, dict)])
        elif isinstance(data, dict) and isinstance(data.get("clusters"), list):
            clusters.extend([c for c in data.get("clusters", []) if isinstance(c, dict)])
    return clusters


def query_cluster_by_name(
    ctx: RunContext,
    *,
    base_url: str,
    token: str,
    cluster_name: str,
    stage_logger,
    api_cfg: Optional[Dict[str, object]] = None,
    cache_result: bool = True,
) -> Dict[str, Any]:
    """查询指定名称的集群，返回匹配集群与完整列表，并可写入 ctx.extra。"""

    timeout = 10
    if isinstance(api_cfg, dict):
        raw_timeout = api_cfg.get("timeout", 10)
        if isinstance(raw_timeout, (int, str)):
            timeout = int(raw_timeout)

    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False

    verify: bool | str = (
    verify_ssl
    if isinstance(verify_ssl, (bool, str))
    else False
    )

    client = APIClient(
        base_url=base_url,
        mock=False,
        timeout=timeout,
        verify=verify,
    )

    headers = {
        "Authorization": token,
        "content-type": "application/json",
    }
    payload = {"where": {"name": cluster_name}}

    stage_logger.info(
        tr("deploy.query_cluster.start"),
        progress_extra={"cluster_name": cluster_name, "base_url": base_url.rstrip("/")},
    )
    stage_logger.debug(
        tr("deploy.query_cluster.request_debug"),
        progress_extra={"payload": payload, "timeout": timeout, "verify_ssl": verify_ssl},
    )

    response = client.post(CLOUDTOWER_GET_CLUSTERS_ENDPOINT, payload=payload, headers=headers)
    clusters = _extract_clusters(response)
    if not clusters:
        raise RuntimeError("CloudTower 未返回任何集群信息")

    target = cluster_name.strip().lower()
    matched = None
    for cluster in clusters:
        name = str(cluster.get("name") or "").strip().lower()
        if name == target:
            matched = cluster
            break

    if not matched:
        raise RuntimeError(f"CloudTower 未找到名为 {cluster_name} 的集群")

    result = {"cluster": matched, "clusters": clusters}

    if cache_result and isinstance(ctx.extra, dict):
        cached = ctx.extra.setdefault("cluster_query", {})
        cached["last_query"] = {"name": cluster_name, "base_url": base_url.rstrip("/")}
        cached["clusters"] = clusters
        cached["cluster"] = matched

    stage_logger.info(
        tr("deploy.query_cluster.done"),
        progress_extra={"cluster_id": matched.get("id"), "connect_state": matched.get("connect_state")},
    )
    return result
