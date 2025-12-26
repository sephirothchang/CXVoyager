"""存储网络 IP 预检逻辑。"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Set

from cxvoyager.utils.network_utils import ProbeResult, ProbeTask, run_probe_tasks
from cxvoyager.models.planning_sheet_models import PlanModel

from .types import ProbeRecord
from .utils import get_section, log_debug, update_level


def _resolve_targets(plan: PlanModel) -> Set[str]:
    targets: Set[str] = set()
    for host in plan.hosts:
        if host.存储地址:
            targets.add(str(host.存储地址))
    return targets


def _resolve_workers(precheck_cfg: Mapping[str, Any], task_count: int) -> int:
    concurrency = int(precheck_cfg.get("concurrency", 8))
    return max(1, min(concurrency, task_count if task_count > 0 else 1))


def inspect(plan: PlanModel, config: Mapping[str, Any], *, logger) -> List[ProbeRecord]:
    """检测存储网段 IP 是否已被占用。"""

    targets = sorted(_resolve_targets(plan))
    records: List[ProbeRecord] = []
    if not targets:
        return records

    precheck_cfg = get_section(config, "precheck")
    storage_cfg = get_section(precheck_cfg, "storage_probe")
    timeout = float(storage_cfg.get("timeout", precheck_cfg.get("storage_timeout", 1.0)))
    retries = int(storage_cfg.get("retries", precheck_cfg.get("storage_retries", 0)))
    extra_ports = storage_cfg.get("ports") or []

    tasks: List[ProbeTask] = []
    for ip in targets:
        tasks.append(ProbeTask(target=ip, kind="icmp", timeout=timeout, retries=retries, metadata={"ip": ip, "probe": "icmp"}))
        for port in extra_ports:
            tasks.append(
                ProbeTask(
                    target=ip,
                    kind="tcp",
                    port=int(port),
                    timeout=timeout,
                    retries=retries,
                    metadata={"ip": ip, "probe": f"tcp_{port}"},
                )
            )

    results = run_probe_tasks(tasks, max_workers=_resolve_workers(precheck_cfg, len(tasks)), logger=logger)

    aggregated: Dict[str, Dict[str, ProbeResult]] = {}
    for result in results:
        ip = result.task.metadata.get("ip") or result.task.target
        label = result.task.metadata.get("probe") or result.task.kind
        aggregated.setdefault(ip, {})[label] = result

    for ip in targets:
        probe_map = aggregated.get(ip, {})
        level = "ok"
        messages: List[str] = []
        detail: Dict[str, Any] = {}

        icmp_result = probe_map.get("icmp")
        if icmp_result:
            detail["icmp"] = icmp_result.to_dict()
            if icmp_result.success:
                level = update_level(level, "error")
                messages.append("存储 IP 已响应 ICMP，可能被占用")
        else:
            messages.append("未获取到 ICMP 探测结果")

        for port in extra_ports:
            key = f"tcp_{port}"
            res = probe_map.get(key)
            if not res:
                continue
            detail[key] = res.to_dict()
            if res.success:
                level = update_level(level, "error")
                messages.append(f"端口 {port} 可达，存储 IP 可能被占用")

        if level == "ok":
            message = "存储 IP 未被占用"
        else:
            message = "；".join(messages)

        record = ProbeRecord(
            category="storage_ip",
            target=ip,
            level=level,
            message=message,
            probes=detail,
        )
        records.append(record)
        log_debug(logger, "存储IP探测详情", {"target": ip, "record": record.to_dict()})

    return records
