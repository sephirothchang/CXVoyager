"""带外 IP 预检逻辑。"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from cxvoyager.common.network_utils import ProbeResult, ProbeTask, run_probe_tasks
from cxvoyager.models.planning_sheet_models import PlanModel

from .types import ProbeRecord
from .utils import get_section, log_debug, update_level


def _resolve_workers(precheck_cfg: Mapping[str, Any], task_count: int) -> int:
    concurrency = int(precheck_cfg.get("concurrency", 8))
    return max(1, min(concurrency, task_count if task_count > 0 else 1))


def inspect(plan: PlanModel, config: Mapping[str, Any], *, logger) -> List[ProbeRecord]:
    """检测带外 IP 的 ICMP 与 623 端口。"""

    targets = [str(host.带外地址) for host in plan.hosts if host.带外地址]
    records: List[ProbeRecord] = []
    if not targets:
        return records

    precheck_cfg = get_section(config, "precheck")
    bmc_cfg = get_section(precheck_cfg, "bmc_probe")
    timeout = float(bmc_cfg.get("timeout", precheck_cfg.get("bmc_timeout", 2.0)))
    retries = int(bmc_cfg.get("retries", precheck_cfg.get("bmc_retries", 0)))
    port = int(bmc_cfg.get("port", precheck_cfg.get("bmc_port", 623)))

    tasks: List[ProbeTask] = []
    for ip in targets:
        tasks.append(ProbeTask(target=ip, kind="icmp", timeout=timeout, retries=retries, metadata={"ip": ip, "probe": "icmp"}))
        tasks.append(
            ProbeTask(
                target=ip,
                kind="tcp",
                port=port,
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
            if not icmp_result.success:
                level = update_level(level, "warning")
                messages.append("ICMP 不可达")
        tcp_result = probe_map.get(f"tcp_{port}")
        if tcp_result:
            detail[f"tcp_{port}"] = tcp_result.to_dict()
            if not tcp_result.success:
                level = update_level(level, "warning")
                messages.append(f"端口 {port} 不可用")

        if not messages:
            message = "带外链路正常"
        else:
            message = "；".join(messages)

        record = ProbeRecord(
            category="bmc_ip",
            target=ip,
            level=level,
            message=message,
            probes=detail,
        )
        records.append(record)
        log_debug(logger, "带外IP探测详情", {"target": ip, "record": record.to_dict()})

    return records
