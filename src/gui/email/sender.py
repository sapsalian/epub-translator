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
    msg["Subject"] = f"[EPUB 번역기] 번역 완료: {epub_filename}"
    msg["From"] = server_config.SMTP_FROM
    msg["To"] = to_email

    plain = (
        f"'{epub_filename}' 번역이 완료되었습니다.\n\n"
        f"다운로드 링크 ({server_config.OUTPUT_RETENTION_HOURS}시간 동안 유효):\n"
        f"{download_url}\n"
    )
    html = f"""\
<html><body>
<p><strong>{epub_filename}</strong> 번역이 완료되었습니다.</p>
<p>
  <a href="{download_url}">번역된 EPUB 다운로드</a>
  &nbsp;(링크 유효 기간: {server_config.OUTPUT_RETENTION_HOURS}시간)
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
    msg["Subject"] = f"[EPUB 번역기] 번역 실패: {epub_filename}"
    msg["From"] = server_config.SMTP_FROM
    msg["To"] = to_email

    plain = (
        f"'{epub_filename}' 번역에 실패했습니다.\n\n"
        f"오류: {error}\n\n"
        "다시 시도하거나 관리자에게 문의해주세요."
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
