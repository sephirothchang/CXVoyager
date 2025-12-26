# SPDX-License-Identifier: GPL-3.0-or-later
"""针对部署载荷生成与部署触发流程的单元测试。"""
from __future__ import annotations

import json
import logging
from ipaddress import ip_address
from pathlib import Path

import pytest

from cxvoyager.workflow.payload_builder import generate_deployment_payload
from cxvoyager.handlers import init_cluster
from cxvoyager.workflow.progress import PROGRESS_MESSAGES_KEY, create_stage_progress_logger
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import Stage
from cxvoyager.models.planning_sheet_models import HostRow, PlanModel


@pytest.fixture()
def minimal_plan() -> PlanModel:
    return PlanModel(
        hosts=[
            HostRow(
                集群名称="My Cluster",
                SMTX主机名="node-01",
                管理地址=ip_address("10.0.0.10"),
                存储地址=ip_address("10.0.1.10"),
            )
        ]
    )


@pytest.fixture()
def minimal_scan_data() -> dict[str, dict]:
    return {
        "10.0.0.10": {
            "host_uuid": "uuid-123",
            "host_ip": "10.0.0.10",
            "ifaces": [
                {"name": "ens224", "hwaddr": "aa:bb", "ipv4": ["10.0.0.10"]},
                {"name": "ens192", "hwaddr": "aa:cc", "ipv4": []},
                {"name": "ens256", "hwaddr": "aa:dd", "ipv4": ["10.0.1.10"]},
                {"name": "ens161", "hwaddr": "aa:ee", "ipv4": []},
            ],
            "disks": [
                {
                    "drive": "sda",
                    "function": "smtx_system",
                    "model": "TestDisk",
                    "serial": "123",
                    "size": 1024,
                    "type": "SSD",
                }
            ],
        }
    }


def test_generate_payload_persists_artifact(tmp_path: Path, minimal_plan: PlanModel, minimal_scan_data: dict[str, dict]) -> None:
    payload, saved_path = generate_deployment_payload(
        plan=minimal_plan,
        host_scan_data=minimal_scan_data,
        parsed_plan=None,
        artifact_dir=tmp_path,
    )

    assert saved_path.parent == tmp_path
    assert "My_Cluster" in saved_path.name or "My" in saved_path.name
    assert saved_path.suffix == ".json"
    assert saved_path.exists()

    with saved_path.open("r", encoding="utf-8") as fh:
        saved_payload = json.load(fh)
    assert saved_payload == payload


def test_vdses_use_plan_switch_ports(tmp_path: Path, minimal_plan: PlanModel, minimal_scan_data: dict[str, dict]) -> None:
    parsed_plan = {
        "_derived_network": {
            "vdses": [
                {
                    "name": "VDS-MGT",
                    "bond": {"mode": "ACTIVE_BACKUP", "nics": ["ens224", "ens192"]},
                },
                {
                    "name": "VDS-SDS",
                    "bond": {"mode": "ACTIVE_BACKUP", "nics": ["ens256", "ens161"]},
                },
            ]
        },
        "virtual_network": {
            "records": [
                {
                    "网络标识": "default",
                    "虚拟交换机": "VDS-MGT",
                    "虚拟机网络": "mgt-net",
                    "subnetwork": "10.0.0.0/24",
                },
                {
                    "网络标识": "storage",
                    "虚拟交换机": "VDS-SDS",
                    "虚拟机网络": "storage-net",
                    "subnetwork": "10.0.1.0/24",
                },
            ]
        },
    }

    payload, _ = generate_deployment_payload(
        plan=minimal_plan,
        host_scan_data=minimal_scan_data,
        parsed_plan=parsed_plan,
        artifact_dir=tmp_path,
    )

    vds_map = {entry["name"]: entry for entry in payload.get("vdses", [])}
    assert vds_map["VDS-MGT"]["hosts_associated"][0]["nics_associated"] == ["ens224", "ens192"]
    assert vds_map["VDS-SDS"]["hosts_associated"][0]["nics_associated"] == ["ens256", "ens161"]


def test_only_management_and_storage_vds_and_networks(tmp_path: Path, minimal_plan: PlanModel, minimal_scan_data: dict[str, dict]) -> None:
    parsed_plan = {
        "_derived_network": {
            "vdses": [
                {
                    "name": "VDS-MGMT-PLAN",
                    "bond": {"mode": "ACTIVE_BACKUP", "nics": ["ens224", "ens192"]},
                },
                {
                    "name": "VDS-SDS-PLAN",
                    "bond": {"mode": "BALANCE_SLB", "nics": ["ens256", "ens161"]},
                },
                {
                    "name": "VDS-BIZ",
                    "bond": {"mode": "ACTIVE_BACKUP", "nics": ["ens500", "ens501"]},
                },
            ]
        },
        "virtual_network": {
            "records": [
                {"网络标识": "default", "虚拟交换机": "VDS-MGMT-PLAN"},
                {"网络标识": "storage", "虚拟交换机": "VDS-SDS-PLAN"},
                {"网络标识": "业务网络", "虚拟交换机": "VDS-BIZ"},
            ]
        },
    }

    payload, _ = generate_deployment_payload(
        plan=minimal_plan,
        host_scan_data=minimal_scan_data,
        parsed_plan=parsed_plan,
        artifact_dir=tmp_path,
    )

    vdses = payload.get("vdses", [])
    assert len(vdses) == 2
    vds_names = {entry["name"] for entry in vdses}
    assert vds_names == {"VDS-MGMT-PLAN", "VDS-SDS-PLAN"}

    networks = payload.get("networks", [])
    assert len(networks) == 2
    network_map = {entry["network_type"]: entry for entry in networks}
    assert network_map["mgt"]["attached_vds"] == "VDS-MGMT-PLAN"
    assert network_map["storage"]["attached_vds"] == "VDS-SDS-PLAN"


def test_trigger_cluster_deployment_uses_first_host(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class DummyClient:
        def __init__(self, base_url: str, mock: bool, timeout: int) -> None:
            self.base_url = base_url
            self.mock = mock
            self.timeout = timeout

        def post(self, path: str, payload: dict, headers: dict | None = None) -> dict:
            calls.append({
                "base_url": self.base_url,
                "path": path,
                "payload": payload,
                "headers": headers or {},
            })
            return {
                "data": {"msg": init_cluster.DEPLOY_SUCCESS_MESSAGE},
                "ec": "EOK",
                "error": {},
            }

    monkeypatch.setattr(init_cluster, "APIClient", DummyClient)

    payload = {
        "platform": "kvm",
        "cluster_name": "cluster",
        "dns_server": [],
        "vdses": [],
        "networks": [],
        "hosts": [],
        "ntp": {"mode": "internal", "ntp_server": None, "current_time": ""},
        "vhost_enabled": True,
        "rdma_enabled": False,
    }

    run_ctx = RunContext()
    stage_logger = create_stage_progress_logger(
        run_ctx,
        Stage.init_cluster.value,
        logger=logging.getLogger("test.init_cluster"),
        prefix="[test]",
    )

    response = init_cluster._trigger_cluster_deployment(  # type: ignore[attr-defined]
        payload=payload,
        host_info={"10.0.0.10": {}},
        token="abc",
        timeout=15,
        base_url_override=None,
        use_mock=False,
        stage_logger=stage_logger,
    )

    assert response == {
        "data": {"msg": init_cluster.DEPLOY_SUCCESS_MESSAGE},
        "ec": "EOK",
        "error": {},
    }
    assert calls, "APIClient.post 应被调用"
    call = calls[0]
    assert call["base_url"] == "http://10.0.0.10"
    assert call["path"] == "/api/v2/deployment/cluster"
    assert call["payload"] == payload
    headers = call["headers"]
    assert headers.get("host") == "10.0.0.10"
    assert headers.get("x-smartx-token") == "abc"
    assert headers.get("content-type") == "application/json"


def test_trigger_cluster_deployment_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyClient:
        def __init__(self, *_, **__):
            pass

        def post(self, *_args, **_kwargs):
            return {"ec": "ERR", "error": {"msg": "invalid"}}

    monkeypatch.setattr(init_cluster, "APIClient", DummyClient)

    with pytest.raises(RuntimeError) as exc:
        init_cluster._trigger_cluster_deployment(  # type: ignore[attr-defined]
            payload={},
            host_info={"10.0.0.10": {}},
            token=None,
            timeout=5,
            base_url_override=None,
            use_mock=False,
            stage_logger=create_stage_progress_logger(
                RunContext(),
                Stage.init_cluster.value,
                logger=logging.getLogger("test.init_cluster"),
                prefix="[test]",
            ),
        )

    assert "ERR" in str(exc.value)


def test_wait_for_deployment_completion_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict | None]] = []
    progress_states = ["running", "success"]
    verify_responses = [{"data": {"is_deployed": False}, "ec": "EOK", "error": {}}, {"data": {"is_deployed": True}, "ec": "EOK", "error": {}}]

    class DummyClient:
        def __init__(self, base_url: str, mock: bool, timeout: int) -> None:
            self.base_url = base_url
            self.mock = mock
            self.timeout = timeout

        def get(self, path: str, params: dict | None = None, headers: dict | None = None) -> dict:
            calls.append((path, params))
            assert headers and headers.get("host") == "10.0.0.10"
            if path == "/api/v2/deployment/host/deploy_status":
                state = progress_states.pop(0)
                return {"data": {"state": state}, "ec": "EOK", "error": {}}
            if path == "/api/v2/deployment/deploy_verify":
                return verify_responses.pop(0)
            raise AssertionError(f"unexpected path {path}")

    sleep_calls: list[int] = []

    def fake_sleep(seconds: int) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(init_cluster, "APIClient", DummyClient)
    monkeypatch.setattr(init_cluster.time, "sleep", fake_sleep)

    run_ctx = RunContext()
    stage_logger = create_stage_progress_logger(
        run_ctx,
        Stage.init_cluster.value,
        logger=logging.getLogger("test.init_cluster"),
        prefix="[test]",
    )
    result = init_cluster._wait_for_deployment_completion(  # type: ignore[attr-defined]
        host_info={"10.0.0.10": {}},
        token="token-1",
        timeout=10,
        base_url_override=None,
        use_mock=False,
        poll_interval=1,
        max_attempts=3,
        stage_logger=stage_logger,
    )

    assert calls[0][0] == "/api/v2/deployment/host/deploy_status"
    assert calls[0][1] == {"host_ip": "10.0.0.10"}
    assert calls[-1][0] == "/api/v2/deployment/deploy_verify"
    assert result["data"]["is_deployed"] is True
    assert sleep_calls[0] == init_cluster.INITIAL_PROGRESS_DELAY
    assert 1 in sleep_calls
    assert init_cluster.VERIFY_POLL_INTERVAL in sleep_calls
    assert run_ctx.extra.get(PROGRESS_MESSAGES_KEY)


def test_wait_for_deployment_completion_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    progress_responses = [{"data": {"state": "success"}, "ec": "EOK", "error": {}}]
    verify_responses = [{"data": {"is_deployed": False}, "ec": "EOK", "error": {"msg": "failed"}}]

    class DummyClient:
        def __init__(self, base_url: str, mock: bool, timeout: int) -> None:
            self.base_url = base_url
            self.mock = mock
            self.timeout = timeout

        def get(self, path: str, params: dict | None = None, headers: dict | None = None) -> dict:
            if path == "/api/v2/deployment/host/deploy_status":
                return progress_responses.pop(0)
            if path == "/api/v2/deployment/deploy_verify":
                return verify_responses.pop(0)
            raise AssertionError(f"unexpected path {path}")

    sleep_calls: list[int] = []

    def fake_sleep(seconds: int) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(init_cluster, "APIClient", DummyClient)
    monkeypatch.setattr(init_cluster.time, "sleep", fake_sleep)

    run_ctx = RunContext()
    stage_logger = create_stage_progress_logger(
        run_ctx,
        Stage.init_cluster.value,
        logger=logging.getLogger("test.init_cluster"),
        prefix="[test]",
    )
    with pytest.raises(RuntimeError) as exc:
        init_cluster._wait_for_deployment_completion(  # type: ignore[attr-defined]
            host_info={"10.0.0.10": {}},
            token=None,
            timeout=5,
            base_url_override=None,
            use_mock=False,
            poll_interval=0,
            max_attempts=2,
            stage_logger=stage_logger,
        )

    assert "部署验证失败" in str(exc.value)
    assert sleep_calls and sleep_calls[0] == init_cluster.INITIAL_PROGRESS_DELAY
    assert run_ctx.extra.get(PROGRESS_MESSAGES_KEY)