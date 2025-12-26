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

"""工作流阶段与调度。"""
from __future__ import annotations
import enum
import logging
from dataclasses import dataclass, replace
from threading import Event
from typing import Any, Callable, Dict, List, Optional
import importlib
import pkgutil
from .runtime_context import RunContext
from cxvoyager.common.i18n import tr

logger = logging.getLogger(__name__)

class Stage(enum.Enum):
    prepare = "prepare"
    init_cluster = "init_cluster"
    config_cluster = "config_cluster"
    deploy_cloudtower = "deploy_cloudtower"
    attach_cluster = "attach_cluster"
    cloudtower_config = "cloudtower_config"
    check_cluster_healthy = "check_cluster_healthy"
    deploy_obs = "deploy_obs"
    deploy_bak = "deploy_bak"
    deploy_er = "deploy_er"
    deploy_sfs = "deploy_sfs"
    deploy_sks = "deploy_sks"
    create_test_vms = "create_test_vms"
    perf_reliability = "perf_reliability"
    cleanup = "cleanup"

Handler = Callable[[Dict[str, Any]], None]
ProgressCallback = Callable[[str, Stage, Optional[RunContext]], None]

_STAGE_HANDLERS: Dict[Stage, Handler] = {}


class AbortRequestedError(RuntimeError):
    """在外部请求终止部署时抛出，用于打断阶段执行。"""


@dataclass(frozen=True)
class StageInfo:
    name: str
    label: str
    description: str
    group: str | None = None
    order: int = 0


_STAGE_METADATA: Dict[Stage, StageInfo] = {
    Stage.prepare: StageInfo(
        name=Stage.prepare.value,
        label="准备与规划校验",
        description="查找规划表、执行结构校验、依赖检测以及基础网络连通性预检。",
        group="前置准备",
    ),
    Stage.init_cluster: StageInfo(
        name=Stage.init_cluster.value,
        label="初始化集群",
        description="创建空集群结构并初始化基础资源。",
        group="集群部署",
    ),
    Stage.config_cluster: StageInfo(
        name=Stage.config_cluster.value,
        label="集群配置",
        description="应用集群网络、安全与资源配置信息。",
        group="集群部署",
    ),
    Stage.deploy_cloudtower: StageInfo(
        name=Stage.deploy_cloudtower.value,
        label="部署 CloudTower",
        description="部署 CloudTower 管理组件并完成基础初始化。",
        group="平台服务",
    ),
    Stage.attach_cluster: StageInfo(
        name=Stage.attach_cluster.value,
        label="接入 CloudTower",
        description="将集群挂载到 CloudTower 并建立安全信任关系。",
        group="平台服务",
    ),
    Stage.cloudtower_config: StageInfo(
        name=Stage.cloudtower_config.value,
        label="CloudTower 配置",
        description="执行 CloudTower 高阶配置与集成策略。",
        group="平台服务",
    ),
    Stage.check_cluster_healthy: StageInfo(
        name=Stage.check_cluster_healthy.value,
        label="集群巡检",
        description="调用 CloudTower 巡检中心执行健康检查并导出报告。",
        group="平台服务",
    ),
    Stage.deploy_obs: StageInfo(
        name=Stage.deploy_obs.value,
        label="部署 OBS",
        description="上传并部署 Observability 应用包。",
        group="业务交付",
    ),
    Stage.deploy_bak: StageInfo(
        name=Stage.deploy_bak.value,
        label="部署 BAK",
        description="上传并部署 Backup 应用包。",
        group="业务交付",
    ),
    Stage.deploy_er: StageInfo(
        name=Stage.deploy_er.value,
        label="部署 ER",
        description="上传并部署 ER 应用包。",
        group="业务交付",
    ),
    Stage.deploy_sfs: StageInfo(
        name=Stage.deploy_sfs.value,
        label="部署 SFS",
        description="上传并部署 SFS 应用包。",
        group="业务交付",
    ),
    Stage.deploy_sks: StageInfo(
        name=Stage.deploy_sks.value,
        label="部署 SKS",
        description="上传并部署 SKS 应用包。",
        group="业务交付",
    ),
    Stage.create_test_vms: StageInfo(
        name=Stage.create_test_vms.value,
        label="创建测试虚机",
        description="创建并配置验证用测试虚拟机。",
        group="验收验证",
    ),
    Stage.perf_reliability: StageInfo(
        name=Stage.perf_reliability.value,
        label="性能与可靠性验证",
        description="执行性能基线与可靠性校验，输出评估报告。",
        group="验收验证",
    ),
    Stage.cleanup: StageInfo(
        name=Stage.cleanup.value,
        label="收尾清理",
        description="配置调优、回收临时资源、清理凭据并归档部署材料。",
        group="收尾",
    ),
}

for index, stage in enumerate(Stage, start=1):
    info = _STAGE_METADATA.get(stage)
    if info is not None:
        if info.order != index:
            _STAGE_METADATA[stage] = replace(info, order=index)
    else:
        _STAGE_METADATA[stage] = StageInfo(
            name=stage.value,
            label=stage.value.replace("_", " ").title(),
            description="",
            order=index,
        )


def get_stage_info(stage: Stage) -> StageInfo:
    return _STAGE_METADATA.get(
        stage,
        StageInfo(
            name=stage.value,
            label=stage.value.replace("_", " ").title(),
            description="",
            order=list(Stage).index(stage) + 1,
        ),
    )


def list_stage_info() -> List[StageInfo]:
    return [get_stage_info(stage) for stage in Stage]


def stage_handler(stage: Stage):  # decorator
    def wrapper(func: Handler):
        _STAGE_HANDLERS[stage] = func
        return func
    return wrapper


def raise_if_aborted(
    ctx: Dict[str, Any],
    *,
    abort_signal: Optional[Event] = None,
    stage_logger: Optional[logging.LoggerAdapter] = None,
    hint: str | None = None,
) -> None:
    """在长耗时流程中检测终止信号，必要时抛出 :class:`AbortRequestedError`。

    该函数会尝试从上下文字典或 ``RunContext.extra`` 中获取终止信号，
    一旦检测到终止请求即记录提示并抛出异常以提前结束阶段。
    """

    signal = abort_signal
    if signal is None:
        signal = ctx.get("abort_signal")
    if signal is None:
        ctx_obj = ctx.get("ctx")
        if isinstance(ctx_obj, RunContext):
            signal = ctx_obj.extra.get("abort_signal")
    if signal is None or not signal.is_set():
        return

    message = tr("deploy.stage_manager.abort_detected")
    if hint:
        message = tr("deploy.stage_manager.abort_detected_hint", hint=hint)
    if stage_logger is not None:
        stage_logger.warning(message)
    else:
        logger.warning(message)
    raise AbortRequestedError("部署任务已被外部终止")


def run_stages(
    selected: List[Stage],
    ctx: Dict[str, Any],
    progress_callback: Optional[ProgressCallback] = None,
    abort_signal: Optional[Event] = None,
) -> None:
    # 动态发现 handlers（只执行一次）
    if not _STAGE_HANDLERS:
        package = __name__.rsplit('.', 1)[0] + '.handlers'
        try:
            pkg = importlib.import_module(package)
        except ImportError:  # pragma: no cover
            logger.error(tr("deploy.stage_manager.import_handlers_failed"))
        else:
            for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
                importlib.import_module(m.name)
    ctx.setdefault("abort_signal", abort_signal)
    for st in selected:
        handler = _STAGE_HANDLERS.get(st)
        if not handler:
            logger.warning(tr("deploy.stage_manager.handler_missing", stage=st.value))
            continue
        if abort_signal is not None and abort_signal.is_set():
            logger.warning(tr("deploy.stage_manager.abort_signal_triggered"))
            raise AbortRequestedError("部署任务已被外部终止")
        logger.info(tr("deploy.stage_manager.start_stage", stage=st.value))
        ctx_obj = ctx.get("ctx")
        run_ctx = ctx_obj if isinstance(ctx_obj, RunContext) else None
        if progress_callback:
            progress_callback("start", st, run_ctx)
        handler(ctx)
        if abort_signal is not None and abort_signal.is_set():
            logger.warning(tr("deploy.stage_manager.abort_during_stage", stage=st.value))
            raise AbortRequestedError("部署任务已被外部终止")
        if isinstance(run_ctx, RunContext):
            run_ctx.completed_stages.append(st.value)
        if progress_callback:
            progress_callback("complete", st, run_ctx)
        logger.info(tr("deploy.stage_manager.end_stage", stage=st.value))

