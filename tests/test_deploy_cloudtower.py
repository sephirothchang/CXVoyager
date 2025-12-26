# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import logging
from pathlib import Path
from threading import Event

import pytest

from cxvoyager.handlers import deploy_cloudtower
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import AbortRequestedError
from cxvoyager.integrations.smartx.api_client import APIError
from cxvoyager.models import PlanModel
from cxvoyager.common.config import Config
from cxvoyager.workflow.progress import PROGRESS_MESSAGES_KEY


class _BaseDummyClient:
    def __init__(self, base_url: str, mock: bool = False, timeout: int = 10):
        self.base_url = base_url
        self.mock = mock
        self.timeout = timeout
        self.create_calls: list[dict] = []
        self.upload_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self.login_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.session_response: dict = {"token": "session-mock"}
        self.session = type("_DummySession", (), {"headers": {}})()

    def post(
        self,
        path: str,
        payload=None,
        *,
        headers=None,
        params=None,
        files=None,
        data=None,
    ):
        raise NotImplementedError

    def get(self, path: str, *, headers=None, params=None):
        raise NotImplementedError

    def delete(self, path: str, *, headers=None, params=None):
        self.delete_calls.append({"path": path, "headers": headers, "params": params})
        return {"ok": True}

    def maybe_handle_session_login(self, path: str, payload=None, headers=None):
        if path == "/api/v3/sessions":
            self.login_calls.append({"payload": payload, "headers": headers})
            return self.session_response
        return None


@pytest.fixture(autouse=True)
def _skip_long_running_vm_steps(monkeypatch: pytest.MonkeyPatch):
    """跳过虚拟机创建与 SSH 安装逻辑，使单元测试聚焦于 ISO 上传等行为。"""

    monkeypatch.setattr(deploy_cloudtower, "_deploy_cloudtower_virtual_machine", lambda **_: None)
    monkeypatch.setattr(deploy_cloudtower, "_install_and_verify_cloudtower_services", lambda **_: None)
    monkeypatch.setattr(
        deploy_cloudtower,
        "_configure_cloudtower_post_install",
        lambda **_: {
            "session": {"token": "mock-token", "username": "root"},
            "organization": {"id": "org-1", "name": "MockOrg"},
            "inputs": {
                "organization_name": "MockOrg",
                "datacenter_name": "Mock-DC",
                "ntp_servers": [],
                "dns_servers": [],
                "cluster_vip": "10.0.0.50",
                "cluster_username": "root",
                "cluster_password": "HC!r0cks",
            },
        },
    )


def _build_context(
    tmp_path: Path,
    iso_name: str,
    *,
    with_host_scan: bool = True,
) -> RunContext:
    plan = PlanModel.model_validate({"mgmt": {"Cloudtower IP": "10.0.0.50"}})
    config = {
        "api": {
            "mock": False,
            "x-smartx-token": "token-123",
            "timeout": 5,
        },
        "cloudtower": {
            "iso_path": iso_name,
            "upload_device": "iscsi",
            "upload_os": "linux",
            "chunk_size_fallback": 4,
        },
    }
    ctx = RunContext(plan=plan, work_dir=tmp_path, config=Config(config))
    if with_host_scan:
        ctx.extra["host_scan"] = {"10.0.0.1": {}}
    return ctx


def test_deploy_cloudtower_uploads_iso(tmp_path, monkeypatch):
    iso_bytes = b"01234567"
    iso_path = tmp_path / "cloudtower-test.iso"
    iso_path.write_bytes(iso_bytes)

    class SuccessfulClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"token": "abc"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self.create_calls.append({"payload": payload, "headers": headers, "params": params})
                assert payload is None
                assert isinstance(headers, dict)
                assert isinstance(params, dict)
                assert params.get("name") == iso_path.name
                assert params.get("size") == len(iso_bytes)
                return {
                    "data": {
                        "image_uuid": "img-123",
                        "zbs_volume_id": "vol-456",
                        "chunk_size": 4,
                        "to_upload": [0, 1],
                    }
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                assert isinstance(params, dict)
                assert isinstance(files, dict)
                assert isinstance(headers, dict)
                assert params["zbs_volume_id"] == "vol-456"
                chunk_num = params["chunk_num"]
                uploaded_chunk = files["file"][1]
                assert headers.get("content-type") is None
                self.upload_calls.append({"chunk": chunk_num, "size": len(uploaded_chunk)})
                return {"data": {"chunk_num": chunk_num, "to_upload": []}}
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

    created_client: dict[str, SuccessfulClient] = {}

    def fake_client_factory(*args, **kwargs):
        client = SuccessfulClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", fake_client_factory)

    ctx = _build_context(tmp_path, iso_path.name)
    deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    client = created_client["instance"]
    assert client.create_calls, "expected volume creation call"
    assert len(client.upload_calls) == 2
    assert {call["chunk"] for call in client.upload_calls} == {0, 1}
    assert client.login_calls, "expected initial Fisheye session login"

    result = ctx.extra["deploy_cloudtower"]
    assert result["status"] == "SERVICE_READY"
    iso_summary = result["iso"]
    assert iso_summary["image_uuid"] == "img-123"
    assert iso_summary["zbs_volume_id"] == "vol-456"
    assert iso_summary["uploaded_chunks"] == 2
    assert iso_summary["file_size"] == len(iso_bytes)
    assert iso_summary["sha256"] == hashlib.sha256(iso_bytes).hexdigest()
    assert result["cloudtower"]["session"]["token"] == "mock-token"


def test_deploy_cloudtower_skips_upload_when_iso_exists(tmp_path, monkeypatch):
    iso_bytes = b"skip-me"
    iso_path = tmp_path / "cloudtower-existing.iso"
    iso_path.write_bytes(iso_bytes)

    class ExistingClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"token": "abc"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {
                    "data": {
                        "images": [
                            {
                                "uuid": "img-existing",
                                "name": iso_path.name,
                                "size": len(iso_bytes),
                                "path": "/nfs/iso/cloudtower-existing.iso",
                                "resource_state": "in-use",
                            }
                        ]
                    }
                }
            raise AssertionError(f"unexpected GET path: {path}")

    created_client: dict[str, ExistingClient] = {}

    def client_factory(*args, **kwargs):
        client = ExistingClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", client_factory)

    ctx = _build_context(tmp_path, iso_path.name)
    deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    client = created_client["instance"]
    assert client.get_calls, "expected ISO existence query"
    assert not client.create_calls, "should skip creating upload volume when ISO exists"
    assert not client.upload_calls, "should skip chunk uploads when ISO exists"
    assert client.login_calls, "expected initial Fisheye session login even when ISO exists"

    iso_summary = ctx.extra["deploy_cloudtower"]["iso"]
    assert iso_summary["image_uuid"] == "img-existing"
    assert iso_summary["file_name"] == iso_path.name
    assert iso_summary["file_size"] == len(iso_bytes)
    assert iso_summary["skipped"] is True
    assert iso_summary["image_path"] == "/nfs/iso/cloudtower-existing.iso"


def test_deploy_cloudtower_upload_respects_abort(tmp_path, monkeypatch):
    iso_bytes = b"abcdefghij"
    iso_path = tmp_path / "cloudtower-abort.iso"
    iso_path.write_bytes(iso_bytes)

    abort_event = Event()

    class AbortingClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"token": "abc"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self.create_calls.append({"headers": headers, "params": params})
                return {
                    "data": {
                        "image_uuid": "img-abort",
                        "zbs_volume_id": "vol-abort",
                        "chunk_size": 4,
                        "to_upload": [0, 1, 2],
                    }
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                params = params or {}
                files = files or {}
                chunk_num = params.get("chunk_num", 0)
                file_entry = files.get("file") or (None, b"")
                payload_bytes = file_entry[1] if isinstance(file_entry, tuple) and len(file_entry) > 1 else b""
                self.upload_calls.append({"chunk": chunk_num, "size": len(payload_bytes)})
                if chunk_num == 0:
                    abort_event.set()
                return {"data": {"chunk_num": chunk_num, "to_upload": [chunk_num + 1]}}
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

    created_client: dict[str, AbortingClient] = {}

    def client_factory(*args, **kwargs):
        client = AbortingClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", client_factory)

    ctx = _build_context(tmp_path, iso_path.name)
    ctx_dict = {"ctx": ctx, "abort_signal": abort_event}

    with pytest.raises(AbortRequestedError):
        deploy_cloudtower.handle_deploy_cloudtower(ctx_dict)

    client = created_client["instance"]
    assert client.upload_calls and len(client.upload_calls) == 1
    assert client.delete_calls, "expected cleanup when upload aborted"
    delete_path = client.delete_calls[0]["path"]
    assert delete_path.endswith("/img-abort")
    assert abort_event.is_set()
    assert client.login_calls, "expected initial Fisheye session login"


def test_deploy_cloudtower_accepts_flat_volume_response(tmp_path, monkeypatch, caplog):
    iso_bytes = b"flat"
    iso_path = tmp_path / "cloudtower-flat.iso"
    iso_path.write_bytes(iso_bytes)

    class FlatClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"token": "flat-token"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self.create_calls.append({"payload": payload, "headers": headers, "params": params})
                assert isinstance(params, dict)
                assert params.get("name") == iso_path.name
                assert params.get("size") == len(iso_bytes)
                return {
                    "image_uuid": "img-flat",
                    "zbs_volume_id": "vol-flat",
                    "chunk_size": 4,
                    "to_upload": [0],
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                params = params or {}
                files = files or {}
                chunk = params.get("chunk_num", 0)
                entry = files.get("file") or (None, b"")
                payload_bytes = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else b""
                self.upload_calls.append({"chunk": chunk, "size": len(payload_bytes)})
                return {"data": {"chunk_num": chunk, "to_upload": []}}
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

    created_client: dict[str, FlatClient] = {}

    def client_factory(*args, **kwargs):
        client = FlatClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", client_factory)
    caplog.set_level(logging.DEBUG, logger="cxvoyager.handlers.deploy_cloudtower")

    ctx = _build_context(tmp_path, iso_path.name)
    deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    client = created_client["instance"]
    assert client.create_calls, "expected volume creation call"
    assert client.upload_calls, "expected upload calls"
    assert client.login_calls, "expected initial Fisheye session login"
    assert any("解析上传卷响应" in message for message in caplog.messages)
    progress_messages = [m for m in caplog.messages if "CloudTower ISO 上传进度" in m]
    assert progress_messages, "expected progress log entries"
    assert any("percentage" in message for message in progress_messages)

    result = ctx.extra["deploy_cloudtower"]
    assert result["iso"]["image_uuid"] == "img-flat"
    assert result["iso"]["zbs_volume_id"] == "vol-flat"

    progress_entries = ctx.extra.get(PROGRESS_MESSAGES_KEY, [])
    assert any(
        entry.get("message") == "CloudTower ISO 上传进度" and entry.get("extra", {}).get("percentage") is not None
        for entry in progress_entries
    ), "progress percentage should be recorded in context"


def test_deploy_cloudtower_without_host_scan_uses_plan_ip(tmp_path, monkeypatch):
    iso_bytes = b"abc123"
    iso_path = tmp_path / "cloudtower-plan.iso"
    iso_path.write_bytes(iso_bytes)

    class FallbackClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"token": "fallback-token"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self.create_calls.append({"payload": payload, "headers": headers, "params": params})
                return {
                    "data": {
                        "image_uuid": "img-plan",
                        "zbs_volume_id": "vol-plan",
                        "chunk_size": 4,
                        "to_upload": [0],
                    }
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                params = params or {}
                files = files or {}
                chunk = params.get("chunk_num", 0)
                chunk_bytes = files.get("file")
                payload_bytes = chunk_bytes[1] if isinstance(chunk_bytes, tuple) and len(chunk_bytes) > 1 else b""
                self.upload_calls.append({"chunk": chunk, "size": len(payload_bytes)})
                return {"data": {"chunk_num": chunk, "to_upload": []}}
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

    created_client: dict[str, FallbackClient] = {}

    def client_factory(*args, **kwargs):
        client = FallbackClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", client_factory)

    ctx = _build_context(tmp_path, iso_path.name, with_host_scan=False)
    deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    client = created_client["instance"]
    assert client.base_url == "http://10.0.0.50"
    assert client.create_calls, "expected volume creation call"
    assert client.upload_calls, "expected chunk upload call"
    assert client.login_calls, "expected initial Fisheye session login"

    result = ctx.extra["deploy_cloudtower"]
    assert result["base_url"] == "http://10.0.0.50"
    assert result["iso"]["image_uuid"] == "img-plan"


def test_deploy_cloudtower_endpoint_uses_host_scan_when_vip_missing(tmp_path, monkeypatch):
    iso_path = tmp_path / "cloudtower-hostscan.iso"
    iso_path.write_bytes(b"xyz")

    class EndpointClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"token": "endpoint-token"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self.create_calls.append({"payload": payload, "headers": headers})
                return {
                    "data": {
                        "image_uuid": "img-host",
                        "zbs_volume_id": "vol-host",
                        "chunk_size": 4,
                        "to_upload": [0],
                    }
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                params = params or {}
                files = files or {}
                chunk = params.get("chunk_num", 0)
                entry = files.get("file") or (None, b"")
                data_bytes = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else b""
                self.upload_calls.append({"chunk": chunk, "size": len(data_bytes)})
                return {"data": {"chunk_num": chunk, "to_upload": []}}
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

    created_client: dict[str, EndpointClient] = {}

    def endpoint_client_factory(*args, **kwargs):
        client = EndpointClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", endpoint_client_factory)

    ctx = _build_context(tmp_path, iso_path.name)
    ctx.plan = PlanModel.model_validate({"mgmt": {}})
    ctx.extra["host_scan"] = {"10.0.0.11": {}, "10.0.0.12": {}}

    deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    client = created_client["instance"]
    assert client.base_url == "http://10.0.0.11"
    assert client.create_calls, "expected volume creation call"
    assert client.upload_calls, "expected chunk upload call"

    result = ctx.extra["deploy_cloudtower"]
    assert result["base_url"] == "http://10.0.0.11"


def test_deploy_cloudtower_upload_failure_triggers_cleanup(tmp_path, monkeypatch):
    iso_path = tmp_path / "cloudtower-test.iso"
    iso_path.write_bytes(b"abcd")

    class FailingClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._created = False
            self.session_response = {"token": "fail-token"}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self._created = True
                return {
                    "data": {
                        "image_uuid": "img-err",
                        "zbs_volume_id": "vol-err",
                        "chunk_size": 4,
                    }
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                raise APIError("upload failed")
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

        def delete(self, path: str, *, headers=None, params=None):
            super().delete(path, headers=headers, params=params)
            return {"data": {"deleted": True}}

    created_client: dict[str, FailingClient] = {}

    def failing_client_factory(*args, **kwargs):
        client = FailingClient(*args, **kwargs)
        created_client["instance"] = client
        return client

    monkeypatch.setattr(deploy_cloudtower, "APIClient", failing_client_factory)

    ctx = _build_context(tmp_path, iso_path.name)
    with pytest.raises(RuntimeError):
        deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    client = created_client["instance"]
    assert client.delete_calls, "expected cleanup DELETE call"
    delete_path = client.delete_calls[0]["path"]
    assert delete_path.endswith("/img-err")


def test_deploy_cloudtower_verifies_fisheye_in_reuse_mode(tmp_path, monkeypatch):
    iso_bytes = b"01234567"
    iso_path = tmp_path / "cloudtower-reuse.iso"
    iso_path.write_bytes(iso_bytes)

    class ReuseClient(_BaseDummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session_response = {"data": {"token": "verify-token"}}

        def post(self, path, payload=None, *, headers=None, params=None, files=None, data=None):
            session = self.maybe_handle_session_login(path, payload, headers)
            if session is not None:
                return session
            if path == deploy_cloudtower.CLOUDTOWER_VOLUME_ENDPOINT:
                self.create_calls.append({"payload": payload, "headers": headers})
                return {
                    "data": {
                        "image_uuid": "img-reuse",
                        "zbs_volume_id": "vol-reuse",
                        "chunk_size": 4,
                        "to_upload": [0],
                    }
                }
            if path == deploy_cloudtower.CLOUDTOWER_UPLOAD_ENDPOINT:
                params = params or {}
                files = files or {}
                chunk = params.get("chunk_num", 0)
                file_entry = files.get("file") or ("", b"")
                chunk_bytes = file_entry[1] if isinstance(file_entry, tuple) and len(file_entry) > 1 else b""
                self.upload_calls.append({"chunk": chunk, "size": len(chunk_bytes)})
                return {"data": {"chunk_num": chunk, "to_upload": []}}
            raise AssertionError(f"unexpected POST path: {path}")

        def get(self, path, *, headers=None, params=None):
            if path == deploy_cloudtower.CLOUDTOWER_IMAGES_ENDPOINT:
                self.get_calls.append({"path": path, "headers": headers, "params": params})
                return {"data": []}
            raise AssertionError(f"unexpected GET path: {path}")

    monkeypatch.setattr(deploy_cloudtower, "APIClient", lambda *args, **kwargs: ReuseClient(*args, **kwargs))

    ctx = _build_context(tmp_path, iso_path.name, with_host_scan=False)
    ctx.extra['selected_stages'] = ["prepare", "deploy_cloudtower"]
    ctx.extra['run_mode'] = 'cloudtower-only'
    ctx.extra['parsed_plan'] = {
        "hosts": {
            "extra": {
                "fisheye_admin_user": "root",
                "fisheye_admin_password": "Passw0rd!",
            }
        }
    }

    deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})

    probes = ctx.extra.get('probes', {})
    assert probes.get('fisheye_login', {}).get('status') == 'ok'
    result = ctx.extra["deploy_cloudtower"]
    assert result["base_url"] == "http://10.0.0.50"
