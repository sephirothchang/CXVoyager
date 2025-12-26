import logging

import pytest
from tenacity import RetryError

from cxvoyager.library.integrations.smartx.api_client import APIClient, APIError


class DummyResponse:
    def __init__(self, status_code: int = 200, text: str = "{\"ok\": true}"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")

    def json(self):
        return {"ok": True}


@pytest.mark.parametrize("status", [200, 401])
def test_post_logs_debug_information(caplog, monkeypatch, status):
    response = DummyResponse(status_code=status, text=f"{{\"status\": {status}}}")
    client = APIClient("http://example.com", mock=False)

    def fake_post(url, **kwargs):
        fake_post.calls.append((url, kwargs))
        return response

    fake_post.calls = []

    monkeypatch.setattr(client.session, "post", fake_post)

    caplog.set_level(logging.DEBUG, logger="cxvoyager.library.integrations.smartx.api_client")

    headers = {"X-SMARTX-TOKEN": "secret-token"}

    if status == 200:
        result = client.post("/test", payload={"foo": "bar"}, headers=headers)
        assert result == {"ok": True}
    else:
        with pytest.raises((APIError, RetryError)):
            client.post("/test", payload={"foo": "bar"}, headers=headers)

    request_logs = [record.message for record in caplog.records if "HTTP POST" in record.message]
    assert request_logs, "expected POST request logs"
    assert any("se***en" in message for message in request_logs)

    response_logs = [record.message for record in caplog.records if "HTTP RESPONSE POST" in record.message]
    assert response_logs, "expected response logs"
    assert any(f"status={status}" in message for message in response_logs)
