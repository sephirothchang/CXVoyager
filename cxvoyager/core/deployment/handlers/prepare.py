# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.
#
# CXVoyager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CXVoyager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CXVoyager.  If not, see <https://www.gnu.org/licenses/>.

# Stage 1 prepare – 准备与规划校验
from __future__ import annotations
import logging
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model
from cxvoyager.core.validation.validator import validate
from cxvoyager.core.deployment.prechecks import run_ip_prechecks
from cxvoyager.common.dependency_checks import check_dependencies
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.common.config import load_config
from cxvoyager.common.i18n import tr

logger = logging.getLogger(__name__)

@stage_handler(Stage.prepare)
def handle_prepare(ctx_dict):
    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(ctx, Stage.prepare.value, logger=logger, prefix="[prepare]")
    stage_logger.info(tr("deploy.prepare.start"))
    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    ctx.config = cfg
    cli_opts = ctx.extra.get('cli_options', {})
    strict_flag = cli_opts.get('strict_validation')
    if strict_flag is None:
        strict_flag = cfg.get('validation', {}).get('strict', False)
    cli_opts['strict_validation'] = bool(strict_flag)
    plan_file = find_plan_file(ctx.work_dir)
    if not plan_file:
        raise RuntimeError(tr("deploy.prepare.plan_file_missing"))
    parsed = parse_plan(plan_file)
    ctx.plan = to_model(parsed)
    ctx.extra.setdefault('parsed_plan', parsed)

    selected_raw = ctx.extra.get('selected_stages') or []
    selected_set = set()
    for item in selected_raw:
        if isinstance(item, Stage):
            selected_set.add(item.value)
        elif isinstance(item, str):
            selected_set.add(item)
    ctx.extra.setdefault('run_mode', 'full')
    if selected_set == {Stage.prepare.value, Stage.deploy_cloudtower.value}:
        ctx.extra['run_mode'] = 'cloudtower-only'
    stage_logger.info(
        tr("deploy.prepare.parse_done"),
        progress_extra={"hosts": len(ctx.plan.hosts), "networks": len(ctx.plan.virtual_network)},
    )

    # 结构验证
    report = validate(parsed)
    if not report.get("ok"):
        stage_logger.error(tr("deploy.prepare.validate_failed"), progress_extra={"errors": report["errors"]})
        raise RuntimeError(tr("deploy.prepare.validate_failed_raise"))
    warnings = report.get("warnings", [])
    if strict_flag and warnings:
        stage_logger.error(tr("deploy.prepare.strict_with_warnings"), progress_extra={"warnings": warnings})
        raise RuntimeError(tr("deploy.prepare.strict_with_warnings_raise"))
    stage_logger.info(tr("deploy.prepare.validate_ok"), progress_extra={"warnings": len(report.get("warnings", []))})

    # 依赖检查
    deps = check_dependencies(optional=True)
    missing = [k for k, v in deps.items() if not v]
    if missing:
        raise RuntimeError(tr("deploy.prepare.deps_missing", missing=missing))
    stage_logger.info(tr("deploy.prepare.deps_ok"))

    # 网络连通性与 IP 占用预检（管理地址、VIP、存储、CloudTower、带外）
    ip_report = run_ip_prechecks(
        ctx,
        stage_logger=stage_logger,
        selected_stages=selected_raw,
    )

    error_records = [r for r in ip_report.records if r.level == "error"]
    warning_records = [r for r in ip_report.records if r.level == "warning"]
    info_records = [r for r in ip_report.records if r.level == "info"]

    if warning_records:
        stage_logger.warning(
            tr("deploy.prepare.precheck_warning"),
            progress_extra={
                "warnings": [r.to_dict() for r in warning_records],
            },
        )
    if info_records:
        stage_logger.info(
            tr("deploy.prepare.precheck_info"),
            progress_extra={
                "infos": [r.to_dict() for r in info_records],
            },
        )
    if error_records:
        stage_logger.error(
            tr("deploy.prepare.precheck_error"),
            progress_extra={
                "errors": [r.to_dict() for r in error_records],
            },
        )
        raise RuntimeError(tr("deploy.prepare.precheck_failed_raise"))

    stage_logger.info(tr("deploy.prepare.precheck_done"), progress_extra={"ip_precheck": ip_report.to_dict()})
    ctx.extra['precheck'] = {
        'deps': deps,
    'network': ip_report.to_dict(),
        'report': report,
        'strict': bool(strict_flag),
        'ip_checks': ip_report.to_dict(),
    }

