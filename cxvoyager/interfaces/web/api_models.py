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

"""Pydantic schemas used by the web API."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Mapping

from pydantic import BaseModel, Field

from cxvoyager.core.deployment.deployment_executor import RunOptions, StageInfo
from cxvoyager.core.deployment.stage_manager import Stage
from cxvoyager.common.config import load_config

from .task_scheduler import TaskRecord, TaskStatus, serialize_task


logger = logging.getLogger(__name__)


def _resolve_default_stage_selection(cfg: Mapping[str, Any] | None = None) -> List[Stage]:
    """读取配置文件中的默认阶段组合，若缺失则回退到 prepare。"""

    data = cfg if isinstance(cfg, Mapping) else load_config()
    web_cfg = data.get("web", {}) if isinstance(data, Mapping) else {}
    defaults_cfg = web_cfg.get("defaults", {}) if isinstance(web_cfg, Mapping) else {}
    stage_names = defaults_cfg.get("stages") if isinstance(defaults_cfg, Mapping) else None
    stages_raw = stage_names if isinstance(stage_names, list) else []

    resolved: List[Stage] = []
    for name in stages_raw:
        try:
            resolved.append(Stage(name))
        except ValueError:
            logger.warning("default.yml 中的默认阶段 %s 无法识别，已忽略。", name)
    if not resolved:
        resolved = [Stage.prepare]
    return resolved


class StageInfoModel(BaseModel):
    name: str
    label: str
    description: str
    group: str | None = None
    order: int

    @classmethod
    def from_dataclass(cls, info: StageInfo) -> "StageInfoModel":
        return cls(**info.__dict__)


class RunOptionsModel(BaseModel):
    dry_run: bool | None = Field(default=None, description="是否仅执行 dry-run")
    strict_validation: bool | None = Field(default=None, description="是否在存在警告时中止")
    debug: bool | None = Field(default=None, description="启用调试日志")

    def to_domain(self) -> RunOptions:
        return RunOptions(**self.model_dump())


def _resolve_default_run_options(cfg: Mapping[str, Any] | None = None) -> RunOptionsModel:
    """结合配置文件解析 Web UI 的运行参数默认值。"""

    data = cfg if isinstance(cfg, Mapping) else load_config()
    web_cfg = data.get("web", {}) if isinstance(data, Mapping) else {}
    defaults_cfg = web_cfg.get("defaults", {}) if isinstance(web_cfg, Mapping) else {}
    raw_options = defaults_cfg.get("run_options") if isinstance(defaults_cfg, Mapping) else None
    options_cfg: Dict[str, Any] = dict(raw_options) if isinstance(raw_options, Mapping) else {}

    if "dry_run" not in options_cfg:
        deploy_cfg = data.get("deploy", {}) if isinstance(data, Mapping) else {}
        if isinstance(deploy_cfg, Mapping):
            options_cfg["dry_run"] = bool(deploy_cfg.get("dry_run", True))
    if "strict_validation" not in options_cfg:
        validation_cfg = data.get("validation", {}) if isinstance(data, Mapping) else {}
        if isinstance(validation_cfg, Mapping):
            options_cfg["strict_validation"] = bool(validation_cfg.get("strict", False))
    if "debug" not in options_cfg:
        logging_cfg = data.get("logging", {}) if isinstance(data, Mapping) else {}
        if isinstance(logging_cfg, Mapping):
            debug_flag = bool(logging_cfg.get("debug", False))
            level = str(logging_cfg.get("level", "INFO")).upper()
            options_cfg["debug"] = debug_flag or level == "DEBUG"

    return RunOptionsModel(**options_cfg)


class UIDefaultsModel(BaseModel):
    """前端加载的 UI 缺省配置。"""

    stages: List[Stage]
    run_options: RunOptionsModel

    @classmethod
    def load(cls) -> "UIDefaultsModel":
        cfg = load_config()
        stages = _resolve_default_stage_selection(cfg)
        run_options = _resolve_default_run_options(cfg)
        return cls(stages=stages, run_options=run_options)


class EffectiveRunOptionsModel(BaseModel):
    dry_run: bool
    strict_validation: bool
    debug: bool
    log_level: str


class StageEventModel(BaseModel):
    event: str
    stage: str
    at: datetime | None = None


class ProgressMessageModel(BaseModel):
    message: str
    stage: str | None = None
    level: str = "info"
    at: datetime | None = None
    extra: Dict[str, Any] | None = None


class RunRequestModel(BaseModel):
    stages: List[Stage] = Field(default_factory=_resolve_default_stage_selection)
    options: RunOptionsModel = Field(default_factory=_resolve_default_run_options)


class RunResponseModel(BaseModel):
    task: "TaskSummaryModel"


class TaskSummaryModel(BaseModel):
    id: str
    status: TaskStatus
    stages: List[Stage]
    requested_options: RunOptionsModel
    effective_options: Optional[EffectiveRunOptionsModel] = None
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    summary: Dict[str, Any] | None = None
    completed_stages: List[str] = Field(default_factory=list)
    total_stages: int = 0
    current_stage: str | None = None
    stage_history: List[StageEventModel] = Field(default_factory=list)
    progress_messages: List[ProgressMessageModel] = Field(default_factory=list)
    abort_requested: bool = False
    abort_reason: str | None = None
    aborted_at: datetime | None = None

    @classmethod
    def from_record(cls, record: TaskRecord) -> "TaskSummaryModel":
        payload = serialize_task(record)
        effective = payload.get("effective_options")
        payload["requested_options"] = RunOptionsModel(**payload["requested_options"])
        if effective:
            payload["effective_options"] = EffectiveRunOptionsModel(**effective)
        else:
            payload["effective_options"] = None
        stage_history = payload.get("stage_history", [])
        payload["stage_history"] = [StageEventModel(**event) for event in stage_history]
        progress_messages = payload.get("progress_messages", [])
        payload["progress_messages"] = [ProgressMessageModel(**msg) for msg in progress_messages]
        return cls(**payload)


class TaskAbortRequest(BaseModel):
    reason: str | None = Field(default=None, description="终止任务的原因说明")


class TaskListResponse(BaseModel):
    items: List[TaskSummaryModel]
    total: int

