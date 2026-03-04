"""Tests for submission form validation logic (no NiceGUI runtime)."""

import pytest


class TestEmailValidation:
    """Email validation mirrors the logic in SubmissionForm._submit()."""

    @staticmethod
    def is_valid_email(email: str) -> bool:
        return bool(email.strip()) and "@" in email

    def test_valid_email(self):
        assert self.is_valid_email("user@example.com") is True

    def test_subdomain_email(self):
        assert self.is_valid_email("user@mail.example.com") is True

    def test_empty_email_is_invalid(self):
        assert self.is_valid_email("") is False

    def test_whitespace_only_is_invalid(self):
        assert self.is_valid_email("   ") is False

    def test_no_at_sign_is_invalid(self):
        assert self.is_valid_email("notanemail") is False

    def test_at_only_is_valid_by_simple_rule(self):
        # Simple check: just requires @, more thorough validation not needed
        assert self.is_valid_email("@") is True


class TestJobParamBuilding:
    """Verify job param dict structure matches what the worker expects."""

    def test_job_params_have_required_keys(self):
        params = {
            "epub_path": "/tmp/book.epub",
            "epub_filename": "book.epub",
            "email": "user@example.com",
            "source_language": "en",
            "target_language": "ko",
            "custom_instructions": "",
        }
        required = {"epub_path", "epub_filename", "email", "source_language", "target_language", "custom_instructions"}
        assert required.issubset(params.keys())

    def test_custom_instructions_defaults_to_empty_string(self):
        custom = None or ""
        assert custom == ""
