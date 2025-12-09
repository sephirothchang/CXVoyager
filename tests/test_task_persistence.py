from datetime import datetime, timezone

from cxvoyager.core.deployment.deployment_executor import RunOptions
from cxvoyager.core.deployment.stage_manager import Stage
from cxvoyager.interfaces.web.task_scheduler import TaskManager, TaskRecord, TaskStatus


def _make_record(task_id: str, stage: Stage, status: TaskStatus) -> TaskRecord:
    record = TaskRecord(id=task_id, stages=[stage], requested_options=RunOptions())
    record.status = status
    record.total_stages = 1
    record.completed_stages = [stage.value] if status == TaskStatus.done else []
    record.current_stage = stage.value if status == TaskStatus.running else None
    now = datetime.now(timezone.utc)
    record.created_at = now
    record.updated_at = now
    record.stage_history.append({
        "event": "complete" if status == TaskStatus.done else "start",
        "stage": stage.value,
        "at": now,
    })
    return record


def test_task_persistence_roundtrip(tmp_path):
    storage_path = tmp_path / "tasks.json"
    manager = TaskManager(storage_path=storage_path)
    record = _make_record("t1", Stage.prepare, TaskStatus.done)
    with manager._lock:
        manager._tasks[record.id] = record
        manager._persist_locked()
    manager._executor.shutdown(wait=False)

    reloaded = TaskManager(storage_path=storage_path)
    loaded = reloaded.get(record.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.done
    assert loaded.completed_stages == [Stage.prepare.value]
    assert loaded.stage_history[0]["at"].tzinfo is not None
    reloaded._executor.shutdown(wait=False)


def test_running_tasks_marked_failed_on_reload(tmp_path):
    storage_path = tmp_path / "tasks.json"
    manager = TaskManager(storage_path=storage_path)
    record = _make_record("running", Stage.prepare, TaskStatus.running)
    with manager._lock:
        manager._tasks[record.id] = record
        manager._persist_locked()
    manager._executor.shutdown(wait=False)

    reloaded = TaskManager(storage_path=storage_path)
    loaded = reloaded.get(record.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.failed
    assert loaded.error == "服务重启时中断"
    assert any(event["event"] == "error" for event in loaded.stage_history)
    reloaded._executor.shutdown(wait=False)
