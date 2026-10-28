"""Email one-time-code (OTP) verification.

Security properties:
  * codes come from `secrets` (CSPRNG) and are stored only as an HMAC-SHA256
    keyed with a secret derived from SECRET_KEY, bound to the user id;
  * comparison is constant-time;
  * a code expires, locks after too many wrong guesses, and is single-use;
  * resends are subject to a cooldown and an hourly cap;
  * the plaintext code is handed only to the mail sender; it is never logged,
    stored, returned from the API, or placed in an exception message.
"""
import hashlib
import hmac
import math
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.email_verification import EmailVerification
from app.models.user import User
from app.services.email_service import EmailDeliveryError, EmailSender
from app.utils.timeutil import as_utc, utc_now


class OtpError(Exception):
    """Base class; messages never contain a code."""


class InvalidOtp(OtpError):
    """Wrong, expired, malformed or missing code (deliberately indistinguishable)."""


class TooManyAttempts(OtpError):
    """The current code is locked; a new one must be requested."""


class ResendTooSoon(OtpError):
    def __init__(self, retry_after: int):
        super().__init__("Please wait before requesting another code")
        self.retry_after = retry_after


class SendLimitReached(OtpError):
    def __init__(self, retry_after: int):
        super().__init__("Too many verification emails requested")
        self.retry_after = retry_after


class AlreadyVerified(OtpError):
    pass


def _hash_code(user_id, code: str) -> str:
    key = hashlib.sha256(b"fitflow-email-otp-v1:" + settings.SECRET_KEY.encode()).digest()
    return hmac.new(key, f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))


async def _get_row(db: AsyncSession, user_id) -> EmailVerification | None:
    result = await db.execute(select(EmailVerification).where(EmailVerification.user_id == user_id))
    return result.scalar_one_or_none()


class EmailVerificationService:

    @staticmethod
    async def issue(db: AsyncSession, user: User, sender: EmailSender) -> None:
        """Create (or replace) the user's code and email it.

        Nothing is committed unless the email was accepted, so a failed send
        leaves no usable code behind and does not start the resend cooldown.
        Raises ResendTooSoon, SendLimitReached or EmailDeliveryError.
        """
        now = utc_now()
        row = await _get_row(db, user.id)

        if row is None:
            row = EmailVerification(user_id=user.id, code_hash="", expires_at=now, attempts=0, send_count=0)
            db.add(row)
        elif row.last_sent_at is not None:
            remaining = settings.OTP_RESEND_COOLDOWN_SECONDS - (now - as_utc(row.last_sent_at)).total_seconds()
            if remaining > 0:
                raise ResendTooSoon(math.ceil(remaining))

        window_start = as_utc(row.send_window_start)
        if window_start is None or now - window_start >= timedelta(hours=1):
            row.send_window_start, row.send_count = now, 0
        elif row.send_count >= settings.OTP_MAX_SENDS_PER_HOUR:
            raise SendLimitReached(math.ceil(3600 - (now - window_start).total_seconds()))

        code = generate_code()
        row.code_hash = _hash_code(user.id, code)
        row.expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        row.attempts = 0

        try:
            await sender.send_verification_code(user.email, code, settings.OTP_EXPIRE_MINUTES)
        except EmailDeliveryError:
            await db.rollback()
            raise

        row.last_sent_at = now
        row.send_count += 1
        await db.commit()

    @staticmethod
    async def verify(db: AsyncSession, user: User, submitted: str) -> None:
        """Confirm the code and mark the user verified.

        Raises AlreadyVerified, TooManyAttempts or InvalidOtp.
        """
        if user.is_verified:
            raise AlreadyVerified()

        row = await _get_row(db, user.id)
        if row is not None and row.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise TooManyAttempts()

        code = (submitted or "").strip()
        well_formed = code.isascii() and code.isdigit() and len(code) == settings.OTP_LENGTH
        if row is None or not well_formed or as_utc(row.expires_at) <= utc_now():
            raise InvalidOtp()

        # Count the guess before comparing so it cannot be skipped by a crash.
        row.attempts += 1
        await db.commit()

        if not hmac.compare_digest(row.code_hash, _hash_code(user.id, code)):
            if row.attempts >= settings.OTP_MAX_ATTEMPTS:
                raise TooManyAttempts()
            raise InvalidOtp()

        user.is_verified = True
        await db.delete(row)          # single use
        await db.commit()
