import logging

from cxvoyager.library.common import logging_config


def test_setup_logging_updates_level(tmp_path, monkeypatch):
    log_path = tmp_path / "cxvoyager.log"
    monkeypatch.setattr(logging_config, "DEFAULT_LOG_FILE", log_path, raising=False)

    logging_config.setup_logging("INFO")
    logging_config.setup_logging("DEBUG")

    logger = logging.getLogger("cxvoyager.tests.logging")
    logger.debug("debug-entry")

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    assert "debug-entry" in log_path.read_text(encoding="utf-8")
