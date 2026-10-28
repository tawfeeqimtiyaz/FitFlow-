"""Outbound email.

Uses the standard-library `smtplib`, so no extra dependency is needed. All
connection details come from settings (environment variables); nothing is
hardcoded. A verification code is only ever passed to `send_verification_code`
and into the message body, never to a logger or an exception.
"""
import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """The provider did not accept the message. Deliberately carries no details."""


class EmailSender:
    """Interface the rest of the app depends on (and that tests replace)."""

    @property
    def is_configured(self) -> bool:
        raise NotImplementedError

    async def send_verification_code(self, to_email: str, code: str, expires_minutes: int) -> None:
        raise NotImplementedError


def _is_valid_address(address) -> bool:
    if not address:
        return False
    name, parsed = parseaddr(address)
    local, _, domain = parsed.partition("@")
    return parsed == address and bool(local) and "." in domain and not domain.startswith(".")


def build_verification_message(to_email: str, code: str, expires_minutes: int) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Your FitFlow verification code"
    message["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM))
    message["To"] = to_email
    message.set_content(
        f"Your FitFlow verification code is: {code}\n\n"
        f"It expires in {expires_minutes} minutes. If you did not create a FitFlow "
        "account, you can ignore this email.\n"
    )
    message.add_alternative(
        f"<p>Your FitFlow verification code is:</p>"
        f"<p style=\"font-size:28px;letter-spacing:6px;font-weight:bold\">{code}</p>"
        f"<p>It expires in {expires_minutes} minutes. If you did not create a FitFlow "
        f"account, you can ignore this email.</p>",
        subtype="html",
    )
    return message


class SmtpEmailSender(EmailSender):
    @property
    def is_configured(self) -> bool:
        return bool(settings.SMTP_HOST) and _is_valid_address(settings.EMAIL_FROM)

    def _send_blocking(self, message: EmailMessage) -> None:
        timeout = settings.SMTP_TIMEOUT_SECONDS
        if settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout,
                context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)

        with server:
            if not settings.SMTP_USE_SSL and settings.SMTP_USE_STARTTLS:
                # Raises (and so aborts the send) if the server cannot upgrade;
                # we never silently fall back to plaintext.
                server.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)

    async def send_verification_code(self, to_email: str, code: str, expires_minutes: int) -> None:
        message = build_verification_message(to_email, code, expires_minutes)
        try:
            await asyncio.to_thread(self._send_blocking, message)
        except (smtplib.SMTPException, OSError) as exc:  # OSError covers timeouts/DNS/refused
            # Log the failure class only: never the message, recipient or code.
            logger.warning("Verification email delivery failed (%s)", type(exc).__name__)
            raise EmailDeliveryError() from None


_default_sender = SmtpEmailSender()


def get_email_sender() -> EmailSender:
    """FastAPI dependency; tests override it with an in-memory fake."""
    return _default_sender
