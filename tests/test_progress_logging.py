import logging

import pytest

from types import SimpleNamespace
from typing import cast

from cxvoyager.library.common.config import Config
from cxvoyager.process.workflow.progress import (
    PROGRESS_MESSAGES_KEY,
    create_stage_progress_logger,
    record_progress,
)
from cxvoyager.process.workflow.runtime_context import RunContext
from cxvoyager.process.workflow.stage_manager import Stage
from cxvoyager.process.handlers.attach_cluster import handle_attach_cluster
from cxvoyager.library.models import PlanModel


def test_record_progress_normalizes_stage_and_level():
    ctx = RunContext()

    record_progress(ctx, "测试消息", stage=Stage.prepare, level="WARNING")  # type: ignore[arg-type]

    messages = ctx.extra.get(PROGRESS_MESSAGES_KEY)
    assert messages is not None
    assert len(messages) == 1

    entry = messages[0]
    assert entry["stage"] == Stage.prepare.value
    assert entry["level"] == "warning"
    assert entry["message"] == "测试消息"
    assert "at" in entry


def test_stage_progress_logger_syncs_progress_and_logger(caplog: pytest.LogCaptureFixture):
    ctx = RunContext()
    base_logger = logging.getLogger("test.progress")

    with caplog.at_level(logging.INFO, logger="test.progress"):
        stage_logger = create_stage_progress_logger(ctx, Stage.prepare.value, logger=base_logger, prefix="[stage]")
        stage_logger.info("同步消息", progress_extra={"foo": "bar"})

    messages = ctx.extra.get(PROGRESS_MESSAGES_KEY)
    assert messages is not None
    assert len(messages) == 1
    entry = messages[0]
    assert entry["level"] == "info"
    assert entry["stage"] == Stage.prepare.value
    assert entry.get("extra") == {"foo": "bar"}

    assert any("[stage] 同步消息" in record.message for record in caplog.records)
    assert any("extra={'foo': 'bar'}" in record.message for record in caplog.records)


def test_stage_handler_uses_progress_logger_integration():
    ctx = RunContext()
    ctx.plan = cast(PlanModel, SimpleNamespace(hosts=[SimpleNamespace()]))
    ctx.extra['deploy_cloudtower'] = {
        'ip': '1.2.3.4',
        'status': 'SERVICE_READY',
        'cloudtower': {
            'organization': {'id': 'org-123'},
            'inputs': {'cluster_vip': '10.20.30.40', 'datacenter_name': 'dc-1'},
            'session': {'token': 'mock-token'},
        },
    }
    ctx.config = Config({'api': {'mock': True}})
    handle_attach_cluster({'ctx': ctx})

    messages = ctx.extra.get(PROGRESS_MESSAGES_KEY)
    assert messages, "进度消息应被记录"
    last_entry = messages[-1]
    assert last_entry['stage'] == Stage.attach_cluster.value
    assert last_entry['level'] == 'info'
    assert last_entry['message'].startswith('Mock 模式') or last_entry['message'].startswith('CloudTower 集群关联成功')
    assert ctx.extra.get('attach_cluster', {}).get('status') == 'SUCCESS'
