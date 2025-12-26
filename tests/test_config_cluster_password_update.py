# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for host password update progress logging."""
from __future__ import annotations

from typing import Any

import pytest

from cxvoyager.handlers import config_cluster
from cxvoyager.workflow.progress import PROGRESS_MESSAGES_KEY, create_stage_progress_logger
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import Stage


@pytest.fixture()
def stage_logger_with_ctx() -> tuple[Any, RunContext]:
    ctx = RunContext()
    logger = create_stage_progress_logger(ctx, Stage.config_cluster)
    return logger, ctx


def _make_host_entries() -> list[dict[str, Any]]:
    return [
        {
            "hostname": "host-01",
            "mgmt_ip": "192.168.56.11",
            "ssh_user": "smartx",
            "ssh_password": "OldPass",
        },
    ]


def test_update_host_passwords_records_mapping_progress_extra(
    monkeypatch: pytest.MonkeyPatch, stage_logger_with_ctx: tuple[Any, RunContext]
) -> None:
    stage_logger, ctx = stage_logger_with_ctx

    monkeypatch.setattr(
        config_cluster.importlib,
        "import_module",
        lambda name: object(),
    )
    monkeypatch.setattr(
        config_cluster,
        "_change_password_via_ssh",
        lambda job, timeout, paramiko_module: {"host": job["host"], "status": "ok"},
    )

    cfg = {"host_password_update": {"enabled": True, "target_password": "NewPass"}}

    summary = config_cluster._update_host_login_passwords(stage_logger, _make_host_entries(), cfg)

    assert summary is not None
    assert summary["status"] == "ok"

    messages = ctx.extra.get(PROGRESS_MESSAGES_KEY, [])
    debug_entries = [entry for entry in messages if entry["message"] == "主机密码更新任务摘要"]
    assert debug_entries, "expected debug progress entry for password update summary"
    extra_payload = debug_entries[0].get("extra")
    assert isinstance(extra_payload, dict), "progress_extra should be stored as a mapping"
    assert "jobs" in extra_payload
    assert isinstance(extra_payload["jobs"], list)
    assert extra_payload["jobs"], "jobs list should not be empty"
