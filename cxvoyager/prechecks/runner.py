"""预检执行器：负责协调各类 IP 检测任务。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Sequence

from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import Stage

from . import bmc_ip, cloudtower_ip, cluster_vip, mgmt_hosts, storage_ip, obs_ip
from .types import PrecheckReport


def _get_logger(stage_logger) -> logging.Logger:
    """根据阶段日志对象返回可用的 logger。"""

    if stage_logger and isinstance(stage_logger, logging.Logger):
        return stage_logger
    return logging.getLogger(__name__)


def run_ip_prechecks(
    ctx: RunContext,
    *,
    stage_logger=None,
    selected_stages: Sequence[str] | None = None,
) -> PrecheckReport:
    """执行所有 IP 预检任务。"""

    logger = _get_logger(stage_logger)
    plan = ctx.plan
    if plan is None:
        raise RuntimeError("运行上下文缺少规划表，无法执行 IP 预检")

    cfg = ctx.config or {}
    stages = list(selected_stages or ctx.extra.get("selected_stages", []))

    report = PrecheckReport()

    stage_set = _as_stage_set(stages)
    app_only = _is_app_only(stage_set)

    report.extend(mgmt_hosts.inspect(plan, cfg, logger=logger))

    if Stage.deploy_obs.value in stage_set:
        report.extend(obs_ip.inspect(plan, cfg, logger=logger))

    if not app_only:
        allow_active_vip = _allow_active_vip(stage_set)
        report.extend(cluster_vip.inspect(plan, cfg, logger=logger, allow_active_vip=allow_active_vip))
        report.extend(cloudtower_ip.inspect(plan, cfg, stages=stages, logger=logger))
    report.extend(storage_ip.inspect(plan, cfg, logger=logger))
    report.extend(bmc_ip.inspect(plan, cfg, logger=logger))

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "IP 预检完成",
            extra={"ip_precheck": json.dumps(report.to_dict(), ensure_ascii=False)},
        )

    return report


def _as_stage_set(stages: Sequence[Any]) -> set[str]:
    stage_set: set[str] = set()
    for stage in stages:
        if isinstance(stage, Stage):
            stage_set.add(stage.value)
        elif isinstance(stage, str):
            stage_set.add(stage)
    return stage_set


def _allow_active_vip(stage_set: set[str]) -> bool:
    return stage_set == {Stage.prepare.value, Stage.deploy_cloudtower.value}


def _is_app_only(stage_set: set[str]) -> bool:
    if not stage_set:
        return False
    app_stages = {
        Stage.prepare.value,
        Stage.deploy_obs.value,
        Stage.deploy_bak.value,
        Stage.deploy_er.value,
        Stage.deploy_sfs.value,
        Stage.deploy_sks.value,
    }
    return stage_set.issubset(app_stages)
