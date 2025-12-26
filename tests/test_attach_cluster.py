# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from cxvoyager.handlers import attach_cluster
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.models import PlanModel


class _ClientRecorder:
    def __init__(self, base_url: str, mock: bool = False, timeout: int = 10):
        self.base_url = base_url
        self.mock = mock
        self.timeout = timeout
        self.calls: list[tuple[str, dict | None, dict | None]] = []

    def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
        if path == attach_cluster.CLOUDTOWER_CREATE_DATACENTER_ENDPOINT:
            self.calls.append(("create-dc", payload, headers))
            info = payload or {}
            return {"data": {"id": "dc-1", "name": info.get("name")}}
        if path == attach_cluster.CLOUDTOWER_CONNECT_CLUSTER_ENDPOINT:
            self.calls.append(("connect", payload, headers))
            return {"data": {"id": "cluster-1"}, "task_id": "task-1"}
        if path == attach_cluster.CLOUDTOWER_GET_CLUSTERS_ENDPOINT:
            self.calls.append(("get-clusters", payload, headers))
            return {
                "clusters": [
                    {
                        "id": "cluster-1",
                        "ip": payload.get("ip") if isinstance(payload, dict) else "10.0.0.210",
                        "connect_state": "CONNECTED",
                    }
                ]
            }
        raise AssertionError(f"unexpected path: {path}")


@pytest.fixture(autouse=True)
def _patch_api_client(monkeypatch):
    created: dict[str, _ClientRecorder] = {}

    def factory(*args, **kwargs):
        client = _ClientRecorder(*args, **kwargs)
        created["instance"] = client
        return client

    monkeypatch.setattr(attach_cluster, "APIClient", factory)
    yield created


def _build_context() -> RunContext:
    plan = PlanModel.model_validate({
        "hosts": [
            {
                "集群名称": "mock",
                "集群VIP": "10.0.0.210",
                "SMTX主机名": "node-1",
                "管理地址": "10.0.0.201",
            }
        ],
        "mgmt": {
            "Cloudtower IP": "10.0.0.50",
            "Cloudtower 组织名称": "MockOrg",
        },
    })
    ctx = RunContext(plan=plan)
    ctx.extra["deploy_cloudtower"] = {
        "status": "SERVICE_READY",
        "ip": "10.0.0.50",
        "cloudtower": {
            "organization": {"id": "org-1", "name": "MockOrg"},
            "session": {"token": "token-abc", "username": "root"},
            "inputs": {
                "datacenter_name": "Mock-DC",
                "cluster_vip": "10.0.0.210",
                "cluster_username": "root",
                "cluster_password": "HC!r0cks",
            },
        },
    }
    return ctx


def test_attach_cluster_success(_patch_api_client):
    ctx = _build_context()
    attach_cluster.handle_attach_cluster({"ctx": ctx})

    result = ctx.extra["attach_cluster"]
    assert result["status"] == "SUCCESS"
    assert result["datacenter"]["id"] == "dc-1"
    assert result["cluster"]["connect_state"].upper() == "CONNECTED"

    client = _patch_api_client["instance"]
    paths = [call[0] for call in client.calls]
    assert paths == ["create-dc", "connect", "get-clusters"]


def test_attach_cluster_requires_deploy_info():
    ctx = RunContext(plan=PlanModel())
    with pytest.raises(RuntimeError):
        attach_cluster.handle_attach_cluster({"ctx": ctx})
