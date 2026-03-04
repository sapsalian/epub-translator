"""Tests for server_config module."""

import os
import importlib
from pathlib import Path
from unittest.mock import patch


_CONFIG_KEYS = [
    "AUTH_USERNAME", "AUTH_PASSWORD", "SECRET_KEY",
    "BASE_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM",
    "OUTPUT_DIR", "UPLOAD_DIR", "CHECKPOINT_DIR", "OUTPUT_RETENTION_HOURS",
]


def _reload_config(env: dict):
    """Reload server_config with a clean environment.

    Clears all config-related env vars, mocks load_dotenv to prevent .env
    from overriding the test environment, then applies the given env dict.
    """
    saved = {k: os.environ.pop(k, None) for k in _CONFIG_KEYS}
    os.environ.update(env)
    try:
        with patch("dotenv.load_dotenv"):  # prevent .env from interfering
            import src.gui.server_config as cfg
            importlib.reload(cfg)
        return cfg
    finally:
        for k in _CONFIG_KEYS:
            os.environ.pop(k, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


class TestServerConfigDefaults:
    def test_default_auth_username(self):
        cfg = _reload_config({})
        assert cfg.AUTH_USERNAME == "admin"

    def test_default_auth_password(self):
        cfg = _reload_config({})
        assert cfg.AUTH_PASSWORD == "changeme"

    def test_default_base_url(self):
        cfg = _reload_config({})
        assert cfg.BASE_URL == "http://localhost:8080"

    def test_default_smtp_host_empty(self):
        cfg = _reload_config({})
        assert cfg.SMTP_HOST == ""

    def test_default_output_dir(self):
        cfg = _reload_config({})
        assert cfg.OUTPUT_DIR == Path("./output")

    def test_default_retention_hours(self):
        cfg = _reload_config({})
        assert cfg.OUTPUT_RETENTION_HOURS == 24


class TestServerConfigEnvOverride:
    def test_auth_username_override(self):
        cfg = _reload_config({"AUTH_USERNAME": "testuser"})
        assert cfg.AUTH_USERNAME == "testuser"

    def test_auth_password_override(self):
        cfg = _reload_config({"AUTH_PASSWORD": "secret"})
        assert cfg.AUTH_PASSWORD == "secret"

    def test_base_url_override(self):
        cfg = _reload_config({"BASE_URL": "https://example.com"})
        assert cfg.BASE_URL == "https://example.com"

    def test_smtp_port_override(self):
        cfg = _reload_config({"SMTP_PORT": "465"})
        assert cfg.SMTP_PORT == 465

    def test_output_dir_override(self):
        cfg = _reload_config({"OUTPUT_DIR": "/tmp/output"})
        assert cfg.OUTPUT_DIR == Path("/tmp/output")

    def test_retention_hours_override(self):
        cfg = _reload_config({"OUTPUT_RETENTION_HOURS": "48"})
        assert cfg.OUTPUT_RETENTION_HOURS == 48
