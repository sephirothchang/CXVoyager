import logging
from pathlib import Path

import pytest

from cxvoyager.core.deployment.prechecks import cloudtower_ip, cluster_vip, mgmt_hosts
from cxvoyager.core.deployment.prechecks.runner import run_ip_prechecks
from cxvoyager.core.deployment.prechecks.types import PrecheckReport, ProbeRecord
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.handlers.prepare import handle_prepare
from cxvoyager.models.planning_sheet_models import PlanModel
from cxvoyager.common.network_utils import ProbeResult, ProbeTask


class DummyStageLogger:
    def __init__(self):
        self.events = []
        self._debug_enabled = False

    def set_debug(self, enabled: bool) -> None:
        self._debug_enabled = enabled

    def isEnabledFor(self, level):
        if level <= logging.DEBUG:
            return self._debug_enabled
        return True

    def debug(self, message, extra=None, **kwargs):
        if self._debug_enabled:
            self.events.append(("debug", message, extra))

    def info(self, message, progress_extra=None, **kwargs):
        self.events.append(("info", message, progress_extra))

    def warning(self, message, progress_extra=None, **kwargs):
        self.events.append(("warning", message, progress_extra))

    def error(self, message, progress_extra=None, **kwargs):
        self.events.append(("error", message, progress_extra))


@pytest.fixture(name="stage_logger")
def stage_logger_fixture():
    return DummyStageLogger()


def test_mgmt_hosts_inspect_levels(monkeypatch):
    plan = PlanModel.model_validate({"hosts": [{"集群名称": "c1", "管理地址": "10.0.0.1"}]})
    config = {"precheck": {"mgmt": {"ports": [80, 443, 22], "timeout": 1, "retries": 0}, "concurrency": 4}}

    def fake_run_probe_tasks(tasks, max_workers=1, logger=None):
        results = []
        for task in tasks:
            if task.kind == "icmp":
                results.append(ProbeResult(task=task, success=True, detail="icmp ok"))
            elif task.kind == "tcp" and task.port == 80:
                results.append(ProbeResult(task=task, success=False, detail="80 down"))
            elif task.kind == "tcp" and task.port == 443:
                results.append(ProbeResult(task=task, success=False, detail="443 not ready"))
            else:
                results.append(ProbeResult(task=task, success=True, detail="port ok"))
        return results

    monkeypatch.setattr(mgmt_hosts, "run_probe_tasks", fake_run_probe_tasks)
    records = mgmt_hosts.inspect(plan, config, logger=logging.getLogger("test"))

    assert len(records) == 1
    record = records[0]
    assert record.level == "error"
    assert "80 端口不可用" in record.message
    assert "443 端口未就绪" in record.message
    assert record.probes["tcp_80"]["success"] is False


def test_cloudtower_inspect_detects_existing_when_stage_selected(monkeypatch):
    plan = PlanModel.model_validate({"mgmt": {"Cloudtower IP": "10.0.0.50"}})
    config = {"precheck": {"cloudtower_probe": {"timeout": 1, "retries": 0, "verify_ssl": False}}}

    def fake_probe_icmp(host, timeout=1.0, retries=0):
        task = ProbeTask(target=host, kind="icmp", timeout=timeout, retries=retries)
        return ProbeResult(task=task, success=True)

    class DummyResponse:
        status_code = 200

        @property
        def text(self):
            return "{\"task_id\": \"abc\", \"data\": {\"token\": \"x\"}}"

        def json(self):
            return {"task_id": "abc", "data": {"token": "x"}}

    monkeypatch.setattr(cloudtower_ip, "probe_icmp", fake_probe_icmp)
    monkeypatch.setattr(cloudtower_ip.httpx, "get", lambda url, timeout, verify: DummyResponse())

    records = cloudtower_ip.inspect(plan, config, stages=["deploy_cloudtower"], logger=logging.getLogger("test"))

    assert len(records) == 1
    record = records[0]
    assert record.level == "error"
    assert "目标 IP 已存在 CloudTower" in record.message
    assert record.probes["http"]["cloudtower_like"] is True


def test_cluster_vip_allows_active_in_cloudtower_only(monkeypatch):
    plan = PlanModel.model_validate({"hosts": [{"集群名称": "c1", "集群VIP": "10.0.0.5"}]})
    config = {"precheck": {"vip_probe": {"timeout": 1, "retries": 0}}}

    def fake_run_probe_tasks(tasks, max_workers=1, logger=None):
        results = []
        for task in tasks:
            success = task.kind == "icmp"
            results.append(ProbeResult(task=task, success=success, detail="ok" if success else "down"))
        return results

    monkeypatch.setattr(cluster_vip, "run_probe_tasks", fake_run_probe_tasks)

    records = cluster_vip.inspect(
        plan,
        config,
        logger=logging.getLogger("test"),
        allow_active_vip=True,
    )

    assert len(records) == 1
    record = records[0]
    assert record.level == "info"
    assert "跳过占用告警" in record.message


def test_handle_prepare_raises_on_ip_errors(monkeypatch, tmp_path, stage_logger):
    ctx = RunContext(work_dir=tmp_path)
    ctx.extra["cli_options"] = {}

    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.create_stage_progress_logger", lambda *args, **kwargs: stage_logger)
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.load_config", lambda *_: {"validation": {"strict": False}})
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.find_plan_file", lambda *_: Path("plan.xlsx"))
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.parse_plan", lambda *_: {"dummy": True})
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.to_model", lambda *_: PlanModel())
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.validate", lambda *_: {"ok": True, "warnings": []})
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.check_dependencies", lambda **kwargs: {})

    error_report = PrecheckReport(records=[ProbeRecord(category="mgmt_host", target="10.0.0.1", level="error", message="失败", probes={})])
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.run_ip_prechecks", lambda *args, **kwargs: error_report)

    with pytest.raises(RuntimeError, match="IP 预检失败"):
        handle_prepare({"ctx": ctx})


def test_handle_prepare_success_sets_ctx_extra(monkeypatch, tmp_path, stage_logger):
    ctx = RunContext(work_dir=tmp_path)
    ctx.extra["cli_options"] = {}

    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.create_stage_progress_logger", lambda *args, **kwargs: stage_logger)
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.load_config", lambda *_: {"validation": {"strict": False}})
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.find_plan_file", lambda *_: Path("plan.xlsx"))
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.parse_plan", lambda *_: {"dummy": True})
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.to_model", lambda *_: PlanModel())
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.validate", lambda *_: {"ok": True, "warnings": []})
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.check_dependencies", lambda **kwargs: {})

    report = PrecheckReport(records=[ProbeRecord(category="mgmt_host", target="10.0.0.1", level="warning", message="提醒", probes={})])
    monkeypatch.setattr("cxvoyager.core.deployment.handlers.prepare.run_ip_prechecks", lambda *args, **kwargs: report)

    handle_prepare({"ctx": ctx})

    assert ctx.plan is not None
    assert "precheck" in ctx.extra
    ip_checks = ctx.extra["precheck"]["ip_checks"]
    assert ip_checks["has_error"] is False
    assert ip_checks["records"][0]["level"] == "warning"


@pytest.mark.parametrize("records, expected", [
    ([], False),
    ([ProbeRecord(category="x", target="t", level="error", message="", probes={})], True),
])
def test_run_ip_prechecks_propagates_has_error(monkeypatch, records, expected):
    ctx = RunContext(plan=PlanModel(), extra={"selected_stages": ["deploy_cloudtower"]})

    monkeypatch.setattr("cxvoyager.core.deployment.prechecks.mgmt_hosts.inspect", lambda *args, **kwargs: [])
    monkeypatch.setattr("cxvoyager.core.deployment.prechecks.cluster_vip.inspect", lambda *args, **kwargs: [])
    monkeypatch.setattr("cxvoyager.core.deployment.prechecks.storage_ip.inspect", lambda *args, **kwargs: [])
    monkeypatch.setattr("cxvoyager.core.deployment.prechecks.cloudtower_ip.inspect", lambda *args, **kwargs: [])
    monkeypatch.setattr("cxvoyager.core.deployment.prechecks.bmc_ip.inspect", lambda *args, **kwargs: records)

    report = run_ip_prechecks(ctx)
    assert report.has_error is expected
