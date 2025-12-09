# SPDX-License-Identifier: GPL-3.0-or-later
"""针对 config_cluster 阶段的单元测试。"""
from __future__ import annotations

from ipaddress import ip_address
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from cxvoyager.common.config import Config
from cxvoyager.core.deployment.handlers import config_cluster
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.integrations.excel import field_variables as plan_vars
from cxvoyager.models.planning_sheet_models import HostRow, PlanModel


class DummyClient:
    def __init__(self, base_url: str, mock: bool, timeout: int) -> None:
        self.base_url = base_url
        self.mock = mock
        self.timeout = timeout
        self.calls: list[tuple[str, str, Any, dict[str, str] | None]] = []

    def post(self, path: str, payload: dict, headers: dict | None = None) -> dict:
        copied_headers = dict(headers or {})
        self.calls.append(("post", path, payload, copied_headers))
        if path == "/api/v3/sessions":
            return {"token": "session-token"}
        return {"ok": True}

    def put(self, path: str, payload: dict, headers: dict | None = None) -> dict:
        copied_headers = dict(headers or {})
        self.calls.append(("put", path, payload, copied_headers))
        return {"ok": True}

    def get(self, path: str, headers: dict | None = None) -> dict:
        copied_headers = dict(headers or {})
        self.calls.append(("get", path, {}, copied_headers))
        return {"data": {"serial": "serial-001"}, "ec": "EOK", "error": {}}


def _prepare_plan(tmp_path: Path) -> Path:
    workbook_path = tmp_path / "plan.xlsx"
    wb = openpyxl.Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.title = plan_vars.CLUSTER_SERIAL.sheet
    sheet[plan_vars.CLUSTER_SERIAL.cell] = ""
    wb.save(workbook_path)
    return workbook_path


def test_run_config_cluster_stage_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workbook_path = _prepare_plan(tmp_path)

    plan = PlanModel(
        hosts=[
            HostRow(
                集群名称="My Cluster",
                集群VIP="10.0.0.50",
                管理地址=ip_address("10.0.0.11"),
                存储地址=ip_address("10.0.1.11"),
                带外地址=ip_address("10.1.0.11"),
                带外用户名="ADMIN",
                带外密码="AdminPass!",
            )
        ],
        source_file=str(workbook_path),
    )

    ctx = RunContext(plan=plan, extra={}, config=Config({"api": {"mock": True, "x-smartx-token": "init-token"}}))
    ctx.extra["deploy_verify"] = {"data": {"is_deployed": True}, "ec": "EOK", "error": {}}
    ctx.extra["host_scan"] = {
        "10.0.0.11": {
            "host_uuid": "uuid-001",
            "hostname": "node-01",
        }
    }

    ctx.extra["parsed_plan"] = {
        "hosts": {
            "extra": {"fisheye_admin_user": "root", "fisheye_admin_password": "Passw0rd!"},
            "records": [
                {
                    "集群VIP": "10.0.0.50",
                    "管理地址": "10.0.0.11",
                    "存储地址": "10.0.1.11",
                    "带外地址": "10.1.0.11",
                    "带外用户名": "ADMIN",
                    "带外密码": "AdminPass!",
                    "主机SSH用户名": "smartx",
                    "主机SSH密码": "NewPass!123",
                }
            ],
        },
        "mgmt": {"records": [{"DNS 服务器": ["8.8.8.8"], "NTP 服务器": ["129.6.15.28"]}]},
        "variables": {
            plan_vars.BUSINESS_VDS_NAME.key: "vDS-Biz",
            plan_vars.BUSINESS_SWITCH_PORTS.key: "ens162,ens194",
            plan_vars.BUSINESS_BOND_MODE.key: "active-backup",
        },
    }

    dummy_client = DummyClient(base_url="http://10.0.0.11", mock=True, timeout=10)
    monkeypatch.setattr(config_cluster, "APIClient", lambda base_url, mock, timeout: dummy_client)

    password_calls: dict[str, Any] = {}

    def fake_password_update(stage_logger, host_entries, cfg):
        password_calls["entries"] = host_entries
        return {"action": "批量更新主机密码", "status": "ok", "success": [entry.get("mgmt_ip") for entry in host_entries]}

    monkeypatch.setattr(config_cluster, "_update_host_login_passwords", fake_password_update)

    config_cluster.run_config_cluster_stage({"ctx": ctx})

    actions = {entry["action"]: entry["status"] for entry in ctx.extra["config_cluster"]["results"]}
    assert actions["初始化 Fisheye 管理员密码"] == "ok"
    assert actions["登录 Fisheye 获取凭证"] == "ok"
    assert actions["配置管理 VIP"] == "ok"
    assert actions["配置 DNS 服务器"] == "ok"
    assert actions["配置 NTP 服务器"] == "ok"
    assert actions["批量配置 IPMI 帐号"] == "ok"
    assert actions["配置业务虚拟交换机"] == "ok"
    assert actions["批量更新主机密码"] == "ok"
    assert actions["获取集群序列号"] == "ok"
    assert ctx.extra["cluster"]["serial"] == "serial-001"

    workbook = openpyxl.load_workbook(workbook_path)
    sheet = workbook[plan_vars.CLUSTER_SERIAL.sheet]
    assert sheet[plan_vars.CLUSTER_SERIAL.cell].value == "serial-001"

    post_calls = [call for call in dummy_client.calls if call[0] == "post"]
    assert any(call[1] == "/api/v3/users:setupRoot" for call in post_calls)
    assert any(call[1] == "/api/v3/sessions" for call in post_calls)
    assert any(call[1] == "/api/v2/ipmi/upsert_accounts" for call in post_calls)
    assert any(call[1] == "/api/v2/network/vds" for call in post_calls)

    put_calls = {call[1]: call for call in dummy_client.calls if call[0] == "put"}
    assert put_calls["/api/v2/settings/vip"][2]["management_vip"] == "10.0.0.50"
    assert put_calls["/api/v2/settings/dns"][2] == {"dns_servers": ["8.8.8.8"]}
    assert put_calls["/api/v2/settings/ntp"][2] == {"ntp_mode": "external", "ntp_servers": ["129.6.15.28"]}

    get_calls = [call for call in dummy_client.calls if call[0] == "get"]
    assert get_calls and get_calls[0][1] == "/api/v2/tools/license"

    assert password_calls["entries"][0]["mgmt_ip"] == "10.0.0.11"


def test_run_config_cluster_stage_requires_deploy_success(tmp_path: Path) -> None:
    plan = PlanModel(hosts=[], source_file=str(_prepare_plan(tmp_path)))
    ctx = RunContext(plan=plan, extra={}, config=Config({"api": {"mock": True}}))

    with pytest.raises(RuntimeError):
        config_cluster.run_config_cluster_stage({"ctx": ctx})


def test_build_ipmi_accounts_payload() -> None:
    host_entries = [
        {
            "mgmt_ip": "10.0.0.11",
            "bmc_ip": "10.1.0.11",
            "bmc_user": "ADMIN",
            "bmc_password": "AdminPass!",
            "hostname": "node-01",
        }
    ]
    host_scan = {"10.0.0.11": {"host_uuid": "uuid-001", "hostname": "node-01"}}
    payload = config_cluster._build_ipmi_accounts_payload(host_entries, host_scan)
    assert payload is not None
    assert payload["accounts"] == [
        {
            "node_uuid": "uuid-001",
            "node_name": "node-01",
            "host": "10.1.0.11",
            "user": "ADMIN",
            "password": "AdminPass!",
        }
    ]


def test_build_business_vds_request_payload() -> None:
    parsed_plan = {
        "variables": {
            plan_vars.BUSINESS_VDS_NAME.key: "vDS-Biz",
            plan_vars.BUSINESS_SWITCH_PORTS.key: "ens162,ens194",
            plan_vars.BUSINESS_BOND_MODE.key: "balance-tcp",
        }
    }
    host_entries = [
        {
            "mgmt_ip": "10.0.0.11",
            "storage_ip": "10.0.1.11",
        }
    ]
    host_scan = {"10.0.0.11": {"host_uuid": "uuid-001", "hostname": "node-01"}}

    payload = config_cluster._build_business_vds_request_payload(parsed_plan, host_entries, host_scan)
    assert payload is not None
    assert payload["name"] == "vDS-Biz"
    assert payload["bond_mode"] == "lacp"
    assert payload["hosts_associated"] == [
        {
            "host_uuid": "uuid-001",
            "nics_associated": ["ens162", "ens194"],
            "data_ip": "10.0.1.11",
        }
    ]


def test_update_host_login_passwords_missing_paramiko(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyLogger:
        def __init__(self) -> None:
            self.records: list[tuple[str, str]] = []

        def info(self, message, progress_extra=None):
            self.records.append(("info", message))

        def warning(self, message, progress_extra=None):
            self.records.append(("warning", message))

        def debug(self, message, progress_extra=None):
            self.records.append(("debug", message))

        def error(self, message, progress_extra=None):
            self.records.append(("error", message))

    def raise_import_error(name: str):  # pragma: no cover - 简单双分支
        raise ImportError()

    monkeypatch.setattr(config_cluster.importlib, "import_module", raise_import_error)

    logger = DummyLogger()
    host_entries = [{"mgmt_ip": "10.0.0.11", "ssh_user": "smartx", "ssh_password": "Pass!"}]
    summary = config_cluster._update_host_login_passwords(logger, host_entries, {})

    assert summary == {
        "action": "批量更新主机密码",
        "status": "failed",
        "error": "missing paramiko",
    }
    assert any(level == "warning" for level, _ in logger.records)
