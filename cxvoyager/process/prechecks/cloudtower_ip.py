"""CloudTower IP 占用检测逻辑。"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

import httpx

from cxvoyager.utils.network_utils import ProbeResult, probe_icmp
from cxvoyager.library.models.planning_sheet_models import PlanModel

from .types import ProbeRecord
from .utils import get_section, log_debug, update_level


def _looks_like_cloudtower(status_code: int | None, data: Any, text_sample: str) -> bool:
    if isinstance(data, dict):
        keys = set(data.keys())
        if {"task_id", "data"}.issubset(keys):
            return True
        if "code" in keys and "message" in keys:
            return True
        if "operationName" in keys or "authMode" in keys:
            return True
    lowered = text_sample.lower()
    return "cloudtower" in lowered


def inspect(
    plan: PlanModel,
    config: Mapping[str, Any],
    *,
    stages: Sequence[str],
    logger,
) -> List[ProbeRecord]:
    """检测 CloudTower IP 是否与规划一致。"""

    records: List[ProbeRecord] = []
    mgmt_info = plan.mgmt
    if not mgmt_info or not mgmt_info.Cloudtower_IP:
        return records

    ip = str(mgmt_info.Cloudtower_IP)
    precheck_cfg = get_section(config, "precheck")
    cloud_cfg = get_section(precheck_cfg, "cloudtower_probe")
    timeout = float(cloud_cfg.get("timeout", 3.0))
    retries = int(cloud_cfg.get("retries", 0))
    verify_ssl = bool(cloud_cfg.get("verify_ssl", False))
    deploy_selected = "deploy_cloudtower" in stages

    detail: Dict[str, Any] = {}
    icmp_result: ProbeResult = probe_icmp(ip, timeout=timeout, retries=retries)
    detail["icmp"] = icmp_result.to_dict()

    cloudtower_like = False
    http_success = False
    http_error: str | None = None
    http_payload: Dict[str, Any] = {}

    url = f"https://{ip}/v2/api/login"
    for attempt in range(retries + 1):
        try:
            resp = httpx.get(url, timeout=timeout, verify=verify_ssl)
            http_success = True
            status = resp.status_code
            text_sample = resp.text[:200] if resp.text else ""
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001 - 允许非 JSON
                data = None
            cloudtower_like = _looks_like_cloudtower(status, data, text_sample)
            http_payload = {
                "status": status,
                "cloudtower_like": cloudtower_like,
                "json": data if isinstance(data, dict) else None,
                "text_sample": text_sample,
            }
            detail["http"] = http_payload
            break
        except httpx.HTTPError as exc:
            http_error = str(exc)
            detail["http_error"] = {"attempt": attempt, "message": http_error}
            continue

    level = "ok"
    messages: List[str] = []

    if not http_success:
        messages.append("未探测到占用，访问接口失败")
    else:
        if cloudtower_like:
            if deploy_selected:
                level = update_level(level, "error")
                messages.append("计划部署 CloudTower，但目标 IP 已存在 CloudTower")
            else:
                level = update_level(level, "info")
                messages.append("检测到现有 CloudTower，保持现状")
        else:
            # 已有其他服务占用该 IP
            if deploy_selected:
                level = update_level(level, "error")
                messages.append("计划部署 CloudTower，但 IP 被其他服务占用")
            else:
                level = update_level(level, "warning")
                messages.append("未计划部署 CloudTower，但 IP 被其他服务占用")
                level = update_level(level, "error")
                detail.setdefault("notes", []).append("warning_promoted_to_error")

    if icmp_result.success and not http_success:
        level = update_level(level, "warning")
        messages.append("ICMP 可达但登录接口不可用，请确认网络")

    message = "；".join(messages) if messages else "CloudTower IP 状态正常"

    record = ProbeRecord(
        category="cloudtower_ip",
        target=ip,
        level=level,
        message=message,
        probes=detail,
    )
    log_debug(logger, "CloudTower探测详情", {"target": ip, "record": record.to_dict()})
    records.append(record)
    return records
