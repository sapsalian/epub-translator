"""Server configuration loaded from environment variables (with .env support)."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env from cwd (or parent dirs) if present
except ImportError:
    pass  # dotenv not installed, env vars must be set manually


def _require(key: str) -> str:
    """Load required environment variable, raise if missing."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set.")
    return value


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# Authentication (single account for demo)
AUTH_USERNAME: str = _optional("AUTH_USERNAME", "admin")
AUTH_PASSWORD: str = _optional("AUTH_PASSWORD", "changeme")
SECRET_KEY: str = _optional("SECRET_KEY", "dev-secret-key-change-in-production")

# Base URL for email links
BASE_URL: str = _optional("BASE_URL", "http://localhost:8080")

# SMTP settings (all optional — if HOST is empty, emails are logged to console)
SMTP_HOST: str = _optional("SMTP_HOST")
SMTP_PORT: int = int(_optional("SMTP_PORT", "587"))
SMTP_USER: str = _optional("SMTP_USER")
SMTP_PASS: str = _optional("SMTP_PASS")
SMTP_FROM: str = _optional("SMTP_FROM", "EPUB Translator <no-reply@example.com>")

# File directories
OUTPUT_DIR: Path = Path(_optional("OUTPUT_DIR", "./output"))
UPLOAD_DIR: Path = Path(_optional("UPLOAD_DIR", "./uploads"))
CHECKPOINT_DIR: Path = Path(_optional("CHECKPOINT_DIR", "./checkpoints"))

# File retention (hours)
OUTPUT_RETENTION_HOURS: int = int(_optional("OUTPUT_RETENTION_HOURS", "24"))
