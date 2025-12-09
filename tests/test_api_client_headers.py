# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from cxvoyager.integrations.smartx.api_client import APIClient


def test_api_client_mock_injects_host_header():
    client = APIClient(base_url="http://10.0.20.210:9443", mock=True)

    get_resp = client.get("/status")
    assert get_resp["headers"]["host"] == "10.0.20.210:9443"

    post_resp = client.post("/api/v2/foo", {"hello": "world"})
    assert post_resp["headers"]["host"] == "10.0.20.210:9443"


def test_api_client_preserves_explicit_host_header():
    client = APIClient(base_url="https://example.com", mock=True)

    resp = client.get("/status", headers={"Host": "custom.host"})
    assert resp["headers"]["Host"] == "custom.host"
    assert "host" not in resp["headers"]


@pytest.mark.parametrize("url,expected", [
    ("http://10.0.0.1", "10.0.0.1"),
    ("https://my-host.local:18443", "my-host.local:18443"),
])
def test_api_client_session_sets_host(url, expected):
    client = APIClient(base_url=url, mock=True)
    assert client.session.headers.get("host") == expected
