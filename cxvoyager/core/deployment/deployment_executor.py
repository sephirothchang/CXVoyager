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

"""Deployment execution helpers shared by CLI and web layers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Event
from typing import Any, Callable, Dict, Iterable, List, Sequence

from cxvoyager.common.config import Config, load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.common.logging_config import setup_logging
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.stage_manager import (
    Stage,
    StageInfo,
    get_stage_info,
    list_stage_info,
    run_stages,
)


logger = logging.getLogger(__name__)


@dataclass
class RunOptions:
    """User provided run options (mirrors CLI flags)."""

    dry_run: bool | None = None
    strict_validation: bool | None = None
    debug: bool | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EffectiveRunOptions:
    """Resolved run options after applying configuration defaults."""

    dry_run: bool
    strict_validation: bool
    debug: bool
    log_level: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunResult:
    """Outcome of a deployment run."""

    completed_stages: List[str]
    options: EffectiveRunOptions
    started_at: datetime
    finished_at: datetime
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completed_stages": self.completed_stages,
            "options": self.options.to_dict(),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "summary": self.summary,
        }


def list_stage_infos() -> List[StageInfo]:
    """Return metadata for all stages in declaration order."""

    return list_stage_info()


def resolve_stages(stage_refs: Iterable[Stage | str]) -> List[Stage]:
    """Normalize user supplied stage references into Stage enums."""

    resolved: List[Stage] = []
    for ref in stage_refs:
        if isinstance(ref, Stage):
            resolved.append(ref)
            continue
        try:
            resolved.append(Stage(ref))
        except ValueError as exc:  # pragma: no cover - validation occurs at boundary
            raise ValueError(f"未知阶段: {ref}") from exc
    return resolved


def execute_run(
    stages: Sequence[Stage],
    options: RunOptions | None = None,
    progress_callback: Callable[[str, Stage, RunContext | None], None] | None = None,
    abort_signal: Event | None = None,
) -> RunResult:
    """Execute the deployment workflow for the requested stages."""

    cfg = load_config(DEFAULT_CONFIG_FILE)
    effective = _resolve_effective_options(cfg, options)
    setup_logging(effective.log_level)

    stage_names = [stage.value if isinstance(stage, Stage) else str(stage) for stage in stages]
    logger.info("加载配置文件: %s", DEFAULT_CONFIG_FILE)
    logger.info("执行阶段: %s", stage_names)
    logger.info("运行参数: %s", effective.to_dict())

    ctx = RunContext(config=cfg)
    ctx.extra.setdefault("cli_options", {})
    ctx.extra["cli_options"].update(
        {
            "dry_run": effective.dry_run,
            "strict_validation": effective.strict_validation,
            "debug": effective.debug,
        }
    )
    ctx.extra["selected_stages"] = [stage.value if isinstance(stage, Stage) else str(stage) for stage in stages]

    started = datetime.now(timezone.utc)

    # run_stages expects a dict containing the RunContext instance under the key "ctx"
    if abort_signal is not None:
        ctx.extra.setdefault("abort_signal", abort_signal)

    run_stages(list(stages), ctx={"ctx": ctx}, progress_callback=progress_callback, abort_signal=abort_signal)

    finished = datetime.now(timezone.utc)
    summary = _build_summary(ctx)
    return RunResult(
        completed_stages=ctx.completed_stages[:],
        options=effective,
        started_at=started,
        finished_at=finished,
        summary=summary,
    )


def _resolve_effective_options(cfg: Config, options: RunOptions | None) -> EffectiveRunOptions:
    provided = options or RunOptions()

    cfg_logging = cfg.get("logging", {}) if isinstance(cfg, dict) else {}
    cfg_validation = cfg.get("validation", {}) if isinstance(cfg, dict) else {}
    cfg_deploy = cfg.get("deploy", {}) if isinstance(cfg, dict) else {}

    strict_default = bool(cfg_validation.get("strict", False))
    dry_run_default = bool(cfg_deploy.get("dry_run", True))

    level = str(cfg_logging.get("level", "INFO")).upper()
    debug_default = bool(cfg_logging.get("debug", False)) or level == "DEBUG"

    strict = strict_default if provided.strict_validation is None else provided.strict_validation
    dry_run = dry_run_default if provided.dry_run is None else provided.dry_run
    debug = debug_default if provided.debug is None else provided.debug

    log_level = "DEBUG" if debug else level

    resolved = EffectiveRunOptions(
        dry_run=dry_run,
        strict_validation=strict,
        debug=debug,
        log_level=log_level,
    )

    logger.debug(
        "解析运行参数: dry_run=%s strict_validation=%s debug=%s log_level=%s",
        resolved.dry_run,
        resolved.strict_validation,
        resolved.debug,
        resolved.log_level,
    )
    return resolved


def _build_summary(ctx: RunContext) -> Dict[str, Any]:
    precheck = ctx.extra.get("precheck", {})
    report = precheck.get("report", {})
    return {
        "strict": precheck.get("strict"),
        "dependencies": precheck.get("deps"),
        "network": precheck.get("network"),
        "report": {
            "ok": report.get("ok"),
            "warnings": report.get("warnings", []),
            "errors": report.get("errors", []),
        },
    }


def stage_to_info(stage: Stage) -> StageInfo:
    return get_stage_info(stage)

