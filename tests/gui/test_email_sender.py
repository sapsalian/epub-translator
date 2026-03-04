"""Tests for email sender (unit, no actual SMTP connection)."""

import importlib
import os
from unittest.mock import AsyncMock, patch

import pytest


def _reload_sender(smtp_host: str = ""):
    """Reload server_config + sender with a clean env and mocked load_dotenv."""
    smtp_env = {"SMTP_HOST": smtp_host} if smtp_host else {}
    # Clear SMTP-related env vars first
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM",
               "AUTH_PASSWORD", "OUTPUT_RETENTION_HOURS", "BASE_URL"):
        os.environ.pop(k, None)
    os.environ.update(smtp_env)
    os.environ.setdefault("SMTP_FROM", "test@example.com")
    os.environ.setdefault("OUTPUT_RETENTION_HOURS", "24")
    os.environ.setdefault("BASE_URL", "http://localhost:8080")

    with patch("dotenv.load_dotenv"):
        import src.gui.server_config as cfg
        importlib.reload(cfg)
        import src.gui.email.sender as sender
        importlib.reload(sender)
    return sender


class TestBuildCompletionMessage:
    def setup_method(self):
        self.sender = _reload_sender()

    def test_subject_contains_filename(self):
        msg = self.sender._build_completion_message(
            "user@example.com", "book.epub", "http://localhost/download/abc"
        )
        assert "book.epub" in msg["Subject"]

    def test_from_header(self):
        msg = self.sender._build_completion_message(
            "user@example.com", "book.epub", "http://localhost/download/abc"
        )
        assert msg["From"] == "test@example.com"

    def test_to_header(self):
        msg = self.sender._build_completion_message(
            "user@example.com", "book.epub", "http://localhost/download/abc"
        )
        assert msg["To"] == "user@example.com"

    def test_body_contains_download_url(self):
        url = "http://localhost/download/abc123"
        msg = self.sender._build_completion_message("u@e.com", "book.epub", url)
        payload = msg.get_payload()
        plain_body = payload[0].get_payload(decode=True).decode("utf-8")
        assert url in plain_body

    def test_html_part_contains_link(self):
        url = "http://localhost/download/abc123"
        msg = self.sender._build_completion_message("u@e.com", "book.epub", url)
        payload = msg.get_payload()
        html_body = payload[1].get_payload(decode=True).decode("utf-8")
        assert url in html_body


class TestBuildFailureMessage:
    def setup_method(self):
        self.sender = _reload_sender()

    def test_subject_contains_filename(self):
        msg = self.sender._build_failure_message("u@e.com", "book.epub", "timeout")
        assert "book.epub" in msg["Subject"]

    def test_body_contains_error(self):
        msg = self.sender._build_failure_message("u@e.com", "book.epub", "API error")
        plain_body = msg.get_payload()[0].get_payload(decode=True).decode("utf-8")
        assert "API error" in plain_body


@pytest.mark.asyncio
class TestSendCompletionEmail:
    async def test_no_smtp_logs_instead_of_sending(self, caplog):
        sender = _reload_sender(smtp_host="")  # no SMTP_HOST
        with caplog.at_level("INFO"):
            await sender.send_completion_email("u@e.com", "book.epub", "token123")
        assert "SMTP not configured" in caplog.text

    async def test_smtp_configured_calls_send_sync(self):
        sender = _reload_sender(smtp_host="smtp.example.com")
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            await sender.send_completion_email("u@e.com", "book.epub", "tok")
            mock_thread.assert_called_once()

    async def test_smtp_failure_is_caught_and_logged(self, caplog):
        sender = _reload_sender(smtp_host="smtp.example.com")
        with patch("asyncio.to_thread", side_effect=Exception("connect refused")):
            with caplog.at_level("ERROR"):
                await sender.send_completion_email("u@e.com", "book.epub", "tok")
        assert "Failed to send" in caplog.text


@pytest.mark.asyncio
class TestSendFailureEmail:
    async def test_no_smtp_logs_instead_of_sending(self, caplog):
        sender = _reload_sender(smtp_host="")  # no SMTP_HOST
        with caplog.at_level("WARNING"):
            await sender.send_failure_email("u@e.com", "book.epub", "some error")
        assert "SMTP not configured" in caplog.text

    async def test_smtp_configured_calls_send_sync(self):
        sender = _reload_sender(smtp_host="smtp.example.com")
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            await sender.send_failure_email("u@e.com", "book.epub", "err")
            mock_thread.assert_called_once()
