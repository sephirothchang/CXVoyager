"""OBS 管理 IP 占用检测逻辑。"""
from __future__ import annotations

import ipaddress
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse

import httpx

from cxvoyager.common.network_utils import ProbeResult, probe_icmp
from cxvoyager.models.planning_sheet_models import PlanModel

from .types import ProbeRecord
from .utils import get_section, log_debug, update_level


def _resolve_target(plan: PlanModel, cfg: Mapping[str, Any]) -> Optional[str]:
    if plan.mgmt and getattr(plan.mgmt, "obs_ip", None):
        return str(plan.mgmt.obs_ip)
    api_cfg = cfg.get("api", {}) if isinstance(cfg, dict) else {}
    base_url = api_cfg.get("obs_base_url") or api_cfg.get("base_url")
    if base_url:
        parsed = urlparse(str(base_url))
        host = parsed.hostname or str(base_url).split(":")[0]
        try:
            ipaddress.ip_address(host)
            return host
        except Exception:
            return None
    return None


def inspect(plan: PlanModel, config: Mapping[str, Any], *, logger) -> List[ProbeRecord]:
    """检测 OBS 管理 IP 是否被占用。

    判定：
    - ICMP 可达或 HTTP 80/443 可达视为被占用，报 error；
    - 无法探测到目标则返回 info。
    """

    target = _resolve_target(plan, config)
    if not target:
        return []

    precheck_cfg = get_section(config, "precheck")
    timeout = float(precheck_cfg.get("vip_timeout", 1.0))
    retries = int(precheck_cfg.get("vip_retries", 0))
    verify_ssl = bool(precheck_cfg.get("verify_ssl", False))

    detail: Dict[str, Any] = {}
    icmp_result: ProbeResult = probe_icmp(target, timeout=timeout, retries=retries)
    detail["icmp"] = icmp_result.to_dict()

    http_ok = False
    http_status: int | None = None
    http_error: str | None = None
    for scheme in ("https", "http"):
        url = f"{scheme}://{target}"
        try:
            resp = httpx.get(url, timeout=timeout, verify=verify_ssl)
            http_ok = True
            http_status = resp.status_code
            detail[f"http_{scheme}"] = {"status": http_status, "text_sample": resp.text[:200] if resp.text else ""}
            break
        except httpx.HTTPError as exc:
            http_error = str(exc)
            detail[f"http_{scheme}_error"] = http_error
            continue

    level = "ok"
    messages: List[str] = []

    if icmp_result.success or http_ok:
        level = update_level(level, "error")
        messages.append("OBS 管理 IP 已被占用")
    else:
        messages.append("未探测到占用")

    record = ProbeRecord(
        category="obs_ip",
        target=target,
        level=level,
        message="；".join(messages),
        probes=detail,
    )
    log_debug(logger, "OBS IP 探测详情", {"target": target, "record": record.to_dict()})
    return [record]
