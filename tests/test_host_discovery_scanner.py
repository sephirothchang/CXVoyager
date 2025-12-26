from ipaddress import ip_address

import pytest

from cxvoyager.process.workflow import host_discovery_scanner as scanner
from cxvoyager.library.models.planning_sheet_models import HostRow, PlanModel, VirtualNetworkRow


class DummyHost:
    SMTX主机名 = "node-1"
    管理地址 = "10.0.0.10"


class FailingClient:
    def __init__(self, *_, **__):
        pass

    def get(self, *_args, **_kwargs):
        raise scanner.APIError("GET http://10.0.0.10 status=401 body=Unauthorized")


def test_scan_single_host_reports_token_hint(monkeypatch):
    monkeypatch.setattr(scanner, "APIClient", lambda *a, **k: FailingClient())
    monkeypatch.setattr(scanner.time, "sleep", lambda *_: None)

    with pytest.raises(RuntimeError) as excinfo:
        scanner._scan_single_host(DummyHost(), token=None, timeout=1, max_retries=1, base_override=None)

    message = str(excinfo.value)
    assert "401" in message
    assert "SmartX API Token" in message
    assert "api.x-smartx-token" in message
    assert "CXVOYAGER_API_TOKEN" in message


def _sample_host_payload(iface_names):
    return {
        "host_ip": "10.0.0.10",
        "host_uuid": "12345678-1234-1234-1234-1234567890ab",
        "hostname": "node-1",
        "ifaces": [
            {"name": name, "hwaddr": f"00:11:22:33:44:{idx:02x}", "ipv4": ["10.0.0.10"]}
            for idx, name in enumerate(iface_names, start=1)
        ],
        "disks": [
            {
                "drive": "sda",
                "function": "boot",
                "model": "model",
                "serial": "serial",
                "size": 256,
                "type": "SSD",
            }
        ],
    }


def test_validate_host_data_respects_plan_nics():
    data = {"data": _sample_host_payload(["ens192", "ens224"])}
    required = {"mgmt": {"ens192", "ens224"}}

    is_valid, errors = scanner._validate_host_data(data, required_ifaces=required)

    assert is_valid is True
    assert errors == []


def test_validate_host_data_reports_missing_nics():
    data = {"data": _sample_host_payload(["ens192"])}
    required = {"mgmt": {"ens192", "ens224"}}

    is_valid, errors = scanner._validate_host_data(data, required_ifaces=required)

    assert is_valid is False
    assert any("管理网卡缺少" in msg and "ens224" in msg for msg in errors)


def test_scan_hosts_emits_warning_for_missing_nic(monkeypatch):
    plan = PlanModel(
        virtual_network=[
            VirtualNetworkRow(
                集群名称="cluster",
                虚拟交换机="管理交换机",
                虚拟机网络="管理网络",
                subnetwork="10.0.0.0/24",
                主机端口="ens192,ens224",
                网口绑定模式="active-backup",
            )
        ],
        hosts=[
            HostRow(
                集群名称="cluster",
                SMTX主机名="node-1",
                管理地址=ip_address("10.0.0.10"),
            )
        ],
        mgmt=None,
        source_file=None,
    )

    class StubClient:
        def __init__(self, *_, **__):
            self.payload = {"data": _sample_host_payload(["ens192"])}

        def get(self, *_args, **_kwargs):
            return self.payload

    monkeypatch.setattr(scanner, "APIClient", lambda *a, **k: StubClient())
    monkeypatch.setattr(scanner.time, "sleep", lambda *_: None)
    monkeypatch.setattr(scanner, "parallel_map", lambda func, items, max_workers=1: [func(item) for item in items])

    results, warnings = scanner.scan_hosts(plan, token=None, timeout=1, max_retries=1)

    assert results == {}
    assert warnings
    assert any("管理网卡缺少" in w and "ens224" in w for w in warnings)
