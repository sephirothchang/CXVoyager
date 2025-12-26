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

"""Background deployment task orchestration for the web API."""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Event, Lock
from typing import Any, Dict, List, Sequence, Tuple
from uuid import uuid4

from cxvoyager.workflow.deployment_executor import EffectiveRunOptions, RunOptions, execute_run
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import AbortRequestedError, Stage

logger = logging.getLogger(__name__)

_DEFAULT_TASK_STORAGE = Path(__file__).resolve().parents[2] / "logs" / "web_tasks.json"
TASK_STORAGE_PATH = Path(os.environ.get("CXVOYAGER_TASK_STORAGE", _DEFAULT_TASK_STORAGE))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    aborted = "aborted"


class TaskAbortedError(RuntimeError):
    """部署任务被用户中止时抛出的异常。"""

    def __init__(self, stage: str | None = None) -> None:
        self.stage = stage
        super().__init__("部署任务已被终止")


@dataclass
class TaskRecord:
    id: str
    stages: List[Stage]
    requested_options: RunOptions
    status: TaskStatus = TaskStatus.pending
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    effective_options: EffectiveRunOptions | None = None
    error: str | None = None
    summary: Dict[str, Any] = field(default_factory=dict)
    completed_stages: List[str] = field(default_factory=list)
    total_stages: int = 0
    current_stage: str | None = None
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    progress_messages: List[Dict[str, Any]] = field(default_factory=list)
    abort_requested: bool = False  # 是否已收到终止请求
    abort_reason: str | None = None  # 终止原因文字描述
    aborted_at: datetime | None = None  # 终止完成时间戳

    def snapshot(self) -> Dict[str, Any]:
        return serialize_task(self)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def serialize_task(record: TaskRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "status": record.status.value,
        "stages": [stage.value if isinstance(stage, Stage) else str(stage) for stage in record.stages],
        "requested_options": record.requested_options.to_dict(),
        "effective_options": record.effective_options.to_dict() if record.effective_options else None,
        "created_at": _serialize_datetime(record.created_at),
        "updated_at": _serialize_datetime(record.updated_at),
        "error": record.error,
        "summary": record.summary,
        "completed_stages": list(record.completed_stages),
        "total_stages": record.total_stages,
        "current_stage": record.current_stage,
        "stage_history": [
            {
                "event": event.get("event"),
                "stage": event.get("stage"),
                "at": _serialize_datetime(event.get("at")),
            }
            for event in record.stage_history
        ],
        "progress_messages": [
            {
                "message": item.get("message"),
                "stage": item.get("stage"),
                "level": item.get("level", "info"),
                "at": _serialize_datetime(item.get("at")),
                "extra": item.get("extra"),
            }
            for item in record.progress_messages
        ],
        "abort_requested": record.abort_requested,
        "abort_reason": record.abort_reason,
        "aborted_at": _serialize_datetime(record.aborted_at),
    }


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _deserialize_task(payload: Dict[str, Any]) -> TaskRecord:
    stages_raw = payload.get("stages", [])
    stages = [Stage(item) if not isinstance(item, Stage) else item for item in stages_raw]
    requested = RunOptions(**payload.get("requested_options", {}))
    record = TaskRecord(
        id=payload["id"],
        stages=stages,
        requested_options=RunOptions(**requested.to_dict()),
        status=TaskStatus(payload.get("status", TaskStatus.pending.value)),
        created_at=_parse_datetime(payload.get("created_at")) or _utcnow(),
        updated_at=_parse_datetime(payload.get("updated_at")) or _utcnow(),
    )
    effective_raw = payload.get("effective_options")
    if effective_raw:
        record.effective_options = EffectiveRunOptions(**effective_raw)
    record.error = payload.get("error")
    record.summary = payload.get("summary", {})
    record.completed_stages = list(payload.get("completed_stages", []))
    record.total_stages = int(payload.get("total_stages", 0))
    record.current_stage = payload.get("current_stage")
    history: List[Dict[str, Any]] = []
    for event in payload.get("stage_history", []):
        at = _parse_datetime(event.get("at"))
        history.append(
            {
                "event": event.get("event"),
                "stage": event.get("stage"),
                "at": at,
            }
        )
    record.stage_history = history
    progress_messages: List[Dict[str, Any]] = []
    for item in payload.get("progress_messages", []):
        at = _parse_datetime(item.get("at"))
        progress_messages.append(
            {
                "message": item.get("message"),
                "stage": item.get("stage"),
                "level": item.get("level", "info"),
                "at": at,
                "extra": item.get("extra"),
            }
        )
    record.progress_messages = progress_messages
    record.abort_requested = bool(payload.get("abort_requested", False))
    record.abort_reason = payload.get("abort_reason")
    record.aborted_at = _parse_datetime(payload.get("aborted_at"))
    return record


class TaskManager:
    def __init__(self, max_workers: int = 4, storage_path: Path | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="deploy-task")
        self._tasks: Dict[str, TaskRecord] = {}
        self._running: Dict[str, Dict[str, Any]] = {}  # 保存正在执行的任务线程信息
        self._lock = Lock()
        self._storage_path = storage_path or TASK_STORAGE_PATH
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:  # pragma: no cover - filesystem interaction
            logger.exception("无法创建任务存档目录: %s", self._storage_path.parent)
        self._load_persisted_tasks()

    def submit(self, stages: Sequence[Stage], options: RunOptions) -> TaskRecord:
        task_id = uuid4().hex
        stage_names = [stage.value if isinstance(stage, Stage) else str(stage) for stage in stages]
        logger.info(
            "提交任务 %s，阶段=%s，选项=%s",
            task_id,
            stage_names,
            options.to_dict(),
        )
        record = TaskRecord(id=task_id, stages=list(stages), requested_options=RunOptions(**options.to_dict()))
        record.total_stages = len(stage_names)
        record.status = TaskStatus.running
        cancel_event = Event()
        with self._lock:
            self._tasks[task_id] = record
            self._running[task_id] = {"cancel_event": cancel_event}
            self._persist_locked()
        logger.debug("任务 %s 已加入线程池队列", task_id)
        future = self._executor.submit(self._run_task, record, cancel_event)
        with self._lock:
            self._running[task_id]["future"] = future
        return record

    def list(self) -> List[TaskRecord]:
        with self._lock:
            return list(self._tasks.values())

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            existed = task_id in self._tasks
            if existed:
                del self._tasks[task_id]
                self._running.pop(task_id, None)
                self._persist_locked()
        if existed:
            logger.info("删除任务记录: %s", task_id)
        return existed

    def abort(self, task_id: str, reason: str | None = None) -> Tuple[TaskRecord | None, bool]:
        """尝试终止指定任务，返回任务快照与终止是否生效。"""

        cancel_event: Event | None = None
        future = None
        reason_text = (reason or "用户主动终止").strip() or "用户主动终止"
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return None, False
            if record.status not in {TaskStatus.pending, TaskStatus.running, TaskStatus.aborted}:
                return record, False
            if record.status == TaskStatus.aborted:
                return record, False
            stage = record.current_stage
            timestamp = _utcnow()
            self._mark_aborted_locked(record, stage, reason_text, timestamp)
            self._persist_locked()
            running_entry = self._running.get(task_id)
            if running_entry:
                cancel_event = running_entry.get("cancel_event")
                future = running_entry.get("future")
        if cancel_event:
            cancel_event.set()
        if future and not future.done():
            future.cancel()
        logger.info("任务 %s 已收到终止请求: %s", task_id, reason_text)
        return record, True

    def _load_persisted_tasks(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            with self._storage_path.open("r", encoding="utf-8") as fh:
                raw_tasks = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("加载任务存档异常，已跳过历史任务: %s", exc)
            return
        dirty = False
        with self._lock:
            for item in raw_tasks or []:
                try:
                    record = _deserialize_task(item)
                except Exception:  # pragma: no cover - unexpected corrupt record
                    logger.exception("跳过损坏的任务记录: %s", item)
                    continue
                if record.status in {TaskStatus.running, TaskStatus.pending}:
                    record.status = TaskStatus.failed
                    record.error = "服务重启时中断"
                    record.updated_at = _utcnow()
                    record.stage_history.append(
                        {
                            "event": "error",
                            "stage": record.current_stage,
                            "at": record.updated_at,
                        }
                    )
                    dirty = True
                self._tasks[record.id] = record
            if dirty:
                self._persist_locked()

    def _persist_locked(self) -> None:
        try:
            payload = [serialize_task(task) for task in self._tasks.values()]
            with self._storage_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception:  # pragma: no cover - filesystem interaction
            logger.exception("写入任务存档失败: %s", self._storage_path)

    def _mark_aborted_locked(
        self,
        record: TaskRecord,
        stage: str | None,
        reason: str | None,
        timestamp: datetime | None = None,
    ) -> None:
        """在持有锁的情况下统一写入终止状态。"""

        ts = timestamp or _utcnow()
        record.status = TaskStatus.aborted
        record.abort_requested = True
        record.abort_reason = reason or record.abort_reason or "用户主动终止"
        record.aborted_at = ts
        record.updated_at = ts
        if stage:
            record.current_stage = stage
        if not any(event.get("event") == "aborted" for event in record.stage_history):
            record.stage_history.append(
                {
                    "event": "aborted",
                    "stage": stage,
                    "at": ts,
                }
            )
        record.error = None

    def _run_task(self, record: TaskRecord, cancel_event: Event) -> None:
        logger.info("任务 %s 开始执行，阶段=%s", record.id, [stage.value for stage in record.stages])

        def _append_progress(event: Dict[str, Any]) -> None:
            """追加阶段日志，保持时间戳一致。"""

            timestamp = event.get("at", _utcnow())
            safe_event = {
                "message": event.get("message"),
                "stage": event.get("stage"),
                "level": event.get("level", "info"),
                "at": timestamp,
                "extra": event.get("extra"),
            }
            with self._lock:
                record.progress_messages.append(safe_event)
                record.updated_at = timestamp
                self._persist_locked()

        def _ensure_not_aborted(stage: Stage | None = None) -> None:
            if cancel_event.is_set():
                raise TaskAbortedError(stage.value if stage else record.current_stage)

        def progress_callback(event: str, stage: Stage, run_ctx) -> None:
            timestamp = _utcnow()
            with self._lock:
                if event == "start":
                    record.current_stage = stage.value
                elif event == "complete":
                    if run_ctx and getattr(run_ctx, "completed_stages", None) is not None:
                        record.completed_stages = list(run_ctx.completed_stages)
                    elif stage.value not in record.completed_stages:
                        record.completed_stages.append(stage.value)
                    if record.total_stages and len(record.completed_stages) >= record.total_stages:
                        record.current_stage = None
                record.stage_history.append(
                    {
                        "event": event,
                        "stage": stage.value,
                        "at": timestamp,
                    }
                )
                record.updated_at = timestamp
                self._persist_locked()
            if run_ctx and isinstance(run_ctx, RunContext):
                sink = run_ctx.extra.get("progress_log_sink")
                if not sink:
                    run_ctx.extra["progress_log_sink"] = _append_progress
            _ensure_not_aborted(stage)

        try:
            _ensure_not_aborted()
            result = execute_run(
                record.stages,
                record.requested_options,
                progress_callback=progress_callback,
                abort_signal=cancel_event,
            )
            if cancel_event.is_set() or record.abort_requested:
                raise TaskAbortedError(record.current_stage)
        except TaskAbortedError as exc:
            with self._lock:
                self._mark_aborted_locked(record, exc.stage, record.abort_reason)
                self._persist_locked()
            logger.info("任务 %s 在阶段 %s 被终止", record.id, exc.stage or "未知阶段")
        except AbortRequestedError:
            with self._lock:
                self._mark_aborted_locked(record, record.current_stage, record.abort_reason)
                self._persist_locked()
            logger.info("任务 %s 在执行过程中检测到终止信号", record.id)
        except Exception as exc:  # pragma: no cover - surfaced to API caller
            with self._lock:
                timestamp = _utcnow()
                record.status = TaskStatus.failed
                record.error = str(exc)
                record.updated_at = timestamp
                if record.current_stage:
                    record.stage_history.append(
                        {
                            "event": "error",
                            "stage": record.current_stage,
                            "at": timestamp,
                        }
                    )
                self._persist_locked()
            logger.exception("任务 %s 执行失败: %s", record.id, exc)
        else:
            with self._lock:
                record.status = TaskStatus.done
                record.effective_options = result.options
                record.summary = result.summary
                record.completed_stages = result.completed_stages
                record.updated_at = result.finished_at
                self._persist_locked()
            duration = (result.finished_at - result.started_at).total_seconds()
            logger.info(
                "任务 %s 执行完成，用时 %.2fs，完成阶段=%s",
                record.id,
                duration,
                result.completed_stages,
            )
        finally:
            with self._lock:
                self._running.pop(record.id, None)


task_manager = TaskManager()

