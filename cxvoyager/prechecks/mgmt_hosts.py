"""管理网主机 IP 预检逻辑。"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from cxvoyager.utils.network_utils import ProbeResult, ProbeTask, run_probe_tasks
from cxvoyager.models.planning_sheet_models import PlanModel

from .types import ProbeRecord
from .utils import get_section, log_debug, update_level


def _resolve_workers(precheck_cfg: Mapping[str, Any], task_count: int) -> int:
    concurrency = int(precheck_cfg.get("concurrency", 8))
    return max(1, min(concurrency, task_count if task_count > 0 else 1))


def inspect(plan: PlanModel, config: Mapping[str, Any], *, logger) -> List[ProbeRecord]:
    """针对规划表中的管理地址执行多协议探测。"""

    records: List[ProbeRecord] = []
    hosts = [host for host in plan.hosts if host.管理地址]
    if not hosts:
        return records

    precheck_cfg = get_section(config, "precheck")
    mgmt_cfg = get_section(precheck_cfg, "mgmt")
    timeout = float(mgmt_cfg.get("timeout", precheck_cfg.get("mgmt_timeout", 2.0)))
    retries = int(mgmt_cfg.get("retries", precheck_cfg.get("mgmt_retries", 0)))
    ports = mgmt_cfg.get("ports") or precheck_cfg.get("mgmt_ports") or [80, 443, 22]

    tasks: List[ProbeTask] = []
    for host in hosts:
        ip = str(host.管理地址)
        tasks.append(
            ProbeTask(target=ip, kind="icmp", timeout=timeout, retries=retries, metadata={"ip": ip, "probe": "icmp"})
        )
        for port in ports:
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

    for host in hosts:
        ip = str(host.管理地址)
        probe_map = aggregated.get(ip, {})
        level = "ok"
        messages: List[str] = []
        detail = {}

        icmp_result = probe_map.get("icmp")
        if icmp_result:
            detail["icmp"] = icmp_result.to_dict()
            if not icmp_result.success:
                level = update_level(level, "error")
                messages.append("ICMP 不可达")

        for port in ports:
            key = f"tcp_{port}"
            res = probe_map.get(key)
            if not res:
                continue
            detail[key] = res.to_dict()
            if port == 80:
                if not res.success:
                    level = update_level(level, "error")
                    messages.append("80 端口不可用")
            elif port == 22:
                if not res.success:
                    level = update_level(level, "warning")
                    messages.append("22 端口不可用")
            elif port == 443:
                if not res.success:
                    level = update_level(level, "info")
                    messages.append("443 端口未就绪")
            else:
                if not res.success:
                    level = update_level(level, "warning")
                    messages.append(f"端口 {port} 不可用")

        message = "；".join(messages) if messages else "管理网络探测通过"
        record = ProbeRecord(
            category="mgmt_host",
            target=ip,
            level=level,
            message=message,
            probes=detail,
        )
        records.append(record)
        log_debug(logger, "管理网探测详情", {"target": ip, "record": record.to_dict()})

    return records
