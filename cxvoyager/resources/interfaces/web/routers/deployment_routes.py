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

"""REST API router for deployment operations."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from ..api_models import (
    TaskAbortRequest,
    RunRequestModel,
    StageInfoModel,
    TaskListResponse,
    TaskSummaryModel,
    UIDefaultsModel,
)
from cxvoyager.process.workflow.deployment_executor import list_stage_infos
from ..task_scheduler import TaskStatus, task_manager

router = APIRouter(prefix="", tags=["deploy"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    logger.debug("健康检查")
    return {"status": "ok"}


@router.get("/stages", response_model=list[StageInfoModel])
def stages() -> list[StageInfoModel]:
    items = [StageInfoModel.from_dataclass(info) for info in list_stage_infos()]
    logger.info("返回阶段列表，共 %d 项", len(items))
    return items


@router.get("/defaults", response_model=UIDefaultsModel)
def ui_defaults() -> UIDefaultsModel:
    defaults = UIDefaultsModel.load()
    stage_names = [stage.value if hasattr(stage, "value") else str(stage) for stage in defaults.stages]
    logger.debug("返回 UI 缺省配置，阶段=%s，选项=%s", stage_names, defaults.run_options.model_dump())
    return defaults


@router.post("/run", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def run(request: RunRequestModel) -> TaskSummaryModel:
    stage_names = [getattr(stage, "value", stage) for stage in request.stages]
    logger.info("创建部署任务，请求阶段=%s，选项=%s", stage_names, request.options.model_dump())
    record = task_manager.submit(request.stages, request.options.to_domain())
    logger.info("任务 %s 已提交", record.id)
    return TaskSummaryModel.from_record(record)


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(status: TaskStatus | None = None) -> TaskListResponse:
    records_raw = task_manager.list()
    if status is not None:
        records_raw = [item for item in records_raw if item.status == status]
        logger.debug("按状态 %s 过滤任务: %d", status.value, len(records_raw))
    else:
        logger.debug("列出所有任务: %d", len(records_raw))
    records = [TaskSummaryModel.from_record(item) for item in records_raw]
    return TaskListResponse(items=records, total=len(records))


@router.get("/tasks/{task_id}", response_model=TaskSummaryModel)
def get_task(task_id: str) -> TaskSummaryModel:
    record = task_manager.get(task_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    logger.debug("获取任务详情: %s", task_id)
    return TaskSummaryModel.from_record(record)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> Response:
    if not task_manager.delete(task_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    logger.info("任务 %s 删除完成", task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tasks/{task_id}/abort", response_model=TaskSummaryModel)
def abort_task(task_id: str, payload: TaskAbortRequest | None = None) -> TaskSummaryModel:
    record, accepted = task_manager.abort(task_id, payload.reason if payload else None)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not accepted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task already finished")
    logger.info("任务 %s 已请求终止", task_id)
    return TaskSummaryModel.from_record(record)

