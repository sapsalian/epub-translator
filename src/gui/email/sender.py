"""Email sender using stdlib smtplib (wrapped in asyncio.to_thread)."""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .. import server_config

logger = logging.getLogger(__name__)


def _build_completion_message(
    to_email: str,
    epub_filename: str,
    download_url: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[EPUB Translator] Translation complete: {epub_filename}"
    msg["From"] = server_config.SMTP_FROM
    msg["To"] = to_email

    plain = (
        f"Your translation of '{epub_filename}' is ready.\n\n"
        f"Download link (valid for {server_config.OUTPUT_RETENTION_HOURS} hours):\n"
        f"{download_url}\n"
    )
    html = f"""\
<html><body>
<p>Your translation of <strong>{epub_filename}</strong> is ready.</p>
<p>
  <a href="{download_url}">Download translated EPUB</a>
  &nbsp;(link valid for {server_config.OUTPUT_RETENTION_HOURS} hours)
</p>
</body></html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def _build_failure_message(
    to_email: str,
    epub_filename: str,
    error: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[EPUB Translator] Translation failed: {epub_filename}"
    msg["From"] = server_config.SMTP_FROM
    msg["To"] = to_email

    plain = (
        f"Translation of '{epub_filename}' failed.\n\n"
        f"Error: {error}\n\n"
        "Please try again or contact the administrator."
    )
    msg.attach(MIMEText(plain, "plain"))
    return msg


def _send_sync(msg: MIMEMultipart) -> None:
    """Send email synchronously via SMTP (called in thread executor)."""
    with smtplib.SMTP(server_config.SMTP_HOST, server_config.SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if server_config.SMTP_USER and server_config.SMTP_PASS:
            smtp.login(server_config.SMTP_USER, server_config.SMTP_PASS)
        smtp.send_message(msg)


async def send_completion_email(
    to_email: str,
    epub_filename: str,
    download_token: str,
) -> None:
    """Send job completion email with a download link.

    If SMTP_HOST is not configured, logs the link to console instead.
    """
    download_url = f"{server_config.BASE_URL}/download/{download_token}"

    if not server_config.SMTP_HOST:
        logger.info(
            "SMTP not configured — would send to %s: %s", to_email, download_url
        )
        return

    msg = _build_completion_message(to_email, epub_filename, download_url)
    try:
        await asyncio.to_thread(_send_sync, msg)
        logger.info("Completion email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send completion email to %s: %s", to_email, exc)


async def send_failure_email(
    to_email: str,
    epub_filename: str,
    error: str,
) -> None:
    """Send job failure email.

    If SMTP_HOST is not configured, logs the error to console instead.
    """
    if not server_config.SMTP_HOST:
        logger.warning(
            "SMTP not configured — would send failure to %s: %s", to_email, error
        )
        return

    msg = _build_failure_message(to_email, epub_filename, error)
    try:
        await asyncio.to_thread(_send_sync, msg)
        logger.info("Failure email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send failure email to %s: %s", to_email, exc)
