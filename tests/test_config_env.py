import os

from cxvoyager.library.common.config import load_config


def test_load_config_uses_env_token(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("api:\n  token: file-token\n", encoding="utf-8")

    monkeypatch.setenv("CXVOYAGER_API_TOKEN", "env-token")

    cfg = load_config(cfg_file)

    assert cfg["api"]["x-smartx-token"] == "env-token"


def test_environment_boolean_and_timeout_overrides(tmp_path, monkeypatch):
    cfg_file = tmp_path / "conf.yml"
    cfg_file.write_text("api:\n  mock: false\n  timeout: 5\n", encoding="utf-8")

    monkeypatch.setenv("CXVOYAGER_API_MOCK", "true")
    monkeypatch.setenv("CXVOYAGER_API_TIMEOUT", "15")
    monkeypatch.setenv("CXVOYAGER_API_BASE_URL", "http://example")

    cfg = load_config(cfg_file)

    assert cfg["api"]["mock"] is True
    assert cfg["api"]["timeout"] == 15
    assert cfg["api"]["base_url"] == "http://example"


def test_smartx_token_fallback(tmp_path, monkeypatch):
    cfg_file = tmp_path / "c.yml"
    cfg_file.write_text("{}", encoding="utf-8")

    monkeypatch.delenv("CXVOYAGER_API_TOKEN", raising=False)
    monkeypatch.setenv("SMARTX_TOKEN", "legacy-token")

    cfg = load_config(cfg_file)

    assert cfg["api"]["x-smartx-token"] == "legacy-token"
