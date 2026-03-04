"""Tests for auth module (logic only, no NiceGUI runtime)."""

import os
import importlib


def _reload_config_with(auth_username: str, auth_password: str):
    os.environ["AUTH_USERNAME"] = auth_username
    os.environ["AUTH_PASSWORD"] = auth_password
    import src.gui.server_config as cfg
    importlib.reload(cfg)
    return cfg


class TestCheckCredentials:
    def setup_method(self):
        _reload_config_with("demo", "s3cr3t")
        import src.gui.auth as auth
        importlib.reload(auth)
        self.auth = auth

    def test_valid_credentials(self):
        assert self.auth.check_credentials("demo", "s3cr3t") is True

    def test_wrong_password(self):
        assert self.auth.check_credentials("demo", "wrong") is False

    def test_wrong_username(self):
        assert self.auth.check_credentials("other", "s3cr3t") is False

    def test_empty_credentials(self):
        assert self.auth.check_credentials("", "") is False

    def test_case_sensitive_username(self):
        assert self.auth.check_credentials("Demo", "s3cr3t") is False

    def test_case_sensitive_password(self):
        assert self.auth.check_credentials("demo", "S3cr3t") is False
