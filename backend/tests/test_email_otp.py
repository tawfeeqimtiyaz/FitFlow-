import asyncio
import contextlib
import io
import logging
import smtplib
import unittest
import uuid
from datetime import timedelta
from unittest import mock

from sqlalchemy import select

from tests.support import client, mailer, run_async

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.email_verification import EmailVerification
from app.models.user import User
from app.services.email_service import EmailDeliveryError, SmtpEmailSender
from app.utils.timeutil import utc_now

PASSWORD = "correct-horse-battery"


def fresh_email(prefix="otp"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def signup(email, password=PASSWORD):
    return client.post("/api/auth/signup", json={"email": email, "password": password})


def verify(email, otp):
    return client.post("/api/auth/verify-otp", json={"email": email, "otp": otp})


def resend(email):
    return client.post("/api/auth/resend-otp", json={"email": email})


def login(email, password=PASSWORD):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def wrong_code_for(real):
    return "000000" if real != "000000" else "111111"


async def _snapshot(email):
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        row = None
        if user is not None:
            row = (
                await db.execute(select(EmailVerification).where(EmailVerification.user_id == user.id))
            ).scalar_one_or_none()
        return user, row


def snapshot(email):
    return run_async(_snapshot, email)


def expire_code(email):
    async def _expire():
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            row = (
                await db.execute(select(EmailVerification).where(EmailVerification.user_id == user.id))
            ).scalar_one()
            row.expires_at = utc_now() - timedelta(minutes=1)
            await db.commit()

    run_async(_expire)


def backdate_account(email, hours):
    async def _backdate():
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.created_at = utc_now() - timedelta(hours=hours)
            await db.commit()

    run_async(_backdate)


class OtpTestCase(unittest.TestCase):
    def setUp(self):
        mailer.reset()

    def assertNoCode(self, text, code):
        self.assertNotIn(code, text, "a verification code leaked into a response/log")


class SignupAndVerificationTests(OtpTestCase):
    def test_signup_creates_unverified_account_and_emails_one_code(self):
        email = fresh_email()
        r = signup(email)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["is_verified"])
        self.assertEqual(len(mailer.codes_for(email)), 1)
        code = mailer.last_code(email)
        self.assertRegex(code, r"^\d{6}$")

    def test_code_never_appears_in_api_responses(self):
        email = fresh_email()
        r = signup(email)
        code = mailer.last_code(email)
        self.assertNoCode(r.text, code)
        self.assertNoCode(verify(email, wrong_code_for(code)).text, code)
        self.assertNoCode(resend(email).text, code)          # cooldown response
        self.assertNoCode(login(email).text, code)

    def test_login_is_blocked_until_the_code_is_verified(self):
        email = fresh_email()
        signup(email)
        self.assertEqual(login(email).status_code, 403)
        json_login = client.post("/api/auth/login/json", json={"email": email, "password": PASSWORD})
        self.assertEqual(json_login.status_code, 403)
        # A wrong password must still look like any other wrong password.
        self.assertEqual(login(email, "not-the-password").status_code, 401)

    def test_successful_verification_enables_login_and_code_is_single_use(self):
        email = fresh_email()
        signup(email)
        code = mailer.last_code(email)

        ok = verify(email, code)
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(login(email).status_code, 200)

        user, row = snapshot(email)
        self.assertTrue(user.is_verified)
        self.assertIsNone(row, "the code must be deleted once used")
        self.assertEqual(verify(email, code).status_code, 400)  # replay is rejected

    def test_unknown_email_looks_the_same_as_a_wrong_code(self):
        email = fresh_email()
        signup(email)
        wrong = verify(email, wrong_code_for(mailer.last_code(email)))
        unknown = verify(fresh_email("ghost"), "123456")
        self.assertEqual(wrong.status_code, unknown.status_code)
        self.assertEqual(wrong.json(), unknown.json())

    def test_user_response_is_verified_flag_after_verification(self):
        email = fresh_email()
        signup(email)
        verify(email, mailer.last_code(email))
        token = login(email).json()["access_token"]
        me = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertTrue(me["is_verified"])


class InvalidAndExpiredCodeTests(OtpTestCase):
    def test_wrong_code_is_rejected_and_the_right_one_still_works(self):
        email = fresh_email()
        signup(email)
        code = mailer.last_code(email)
        bad = verify(email, wrong_code_for(code))
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["detail"], "Invalid or expired verification code")
        self.assertEqual(verify(email, code).status_code, 200)

    def test_malformed_codes_are_rejected_without_using_up_attempts(self):
        email = fresh_email()
        signup(email)
        code = mailer.last_code(email)
        for junk in ("", "12345", "1234567", "abcdef", "12 456", "١٢٣٤٥٦", "<script>"):
            with self.subTest(otp=junk):
                r = verify(email, junk)
                self.assertEqual(r.status_code, 400)
                if junk:
                    self.assertNotIn(junk, r.text)                   # submitted values are never echoed
        self.assertEqual(verify(email, code).status_code, 200)

    def test_expired_code_is_rejected_and_a_resend_recovers(self):
        email = fresh_email()
        signup(email)
        old = mailer.last_code(email)
        expire_code(email)
        self.assertEqual(verify(email, old).status_code, 400)

        with mock.patch.object(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0):
            self.assertEqual(resend(email).status_code, 200)
        self.assertEqual(verify(email, mailer.last_code(email)).status_code, 200)

    def test_too_many_wrong_guesses_lock_the_code_until_a_new_one_is_sent(self):
        email = fresh_email()
        signup(email)
        real = mailer.last_code(email)
        bad = wrong_code_for(real)

        for _ in range(settings.OTP_MAX_ATTEMPTS - 1):
            self.assertEqual(verify(email, bad).status_code, 400)
        self.assertEqual(verify(email, bad).status_code, 429)       # the last allowed guess locks it
        locked = verify(email, real)                                # even the right code is refused now
        self.assertEqual(locked.status_code, 429)
        self.assertNoCode(locked.text, real)
        self.assertFalse(snapshot(email)[0].is_verified)

        with mock.patch.object(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0):
            self.assertEqual(resend(email).status_code, 200)
        self.assertEqual(verify(email, mailer.last_code(email)).status_code, 200)

    def test_code_is_stored_only_as_a_keyed_hash(self):
        email = fresh_email()
        signup(email)
        code = mailer.last_code(email)
        _, row = snapshot(email)
        self.assertEqual(len(row.code_hash), 64)
        int(row.code_hash, 16)                                       # valid hex digest
        self.assertNotEqual(row.code_hash, code)
        self.assertNotIn(code, row.code_hash)
        self.assertEqual(row.attempts, 0)
        self.assertGreater(row.expires_at.replace(tzinfo=None), utc_now().replace(tzinfo=None))


class ResendTests(OtpTestCase):
    def test_resend_replaces_the_code(self):
        email = fresh_email()
        signup(email)
        first = mailer.last_code(email)
        with mock.patch.object(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0):
            self.assertEqual(resend(email).status_code, 200)
        second = mailer.last_code(email)
        self.assertEqual(len(mailer.codes_for(email)), 2)
        if first != second:                                          # (1-in-a-million collision otherwise)
            self.assertEqual(verify(email, first).status_code, 400)
        self.assertEqual(verify(email, second).status_code, 200)

    def test_resend_cooldown_is_enforced(self):
        email = fresh_email()
        signup(email)
        r = resend(email)
        self.assertEqual(r.status_code, 429)
        self.assertGreater(int(r.headers["Retry-After"]), 0)
        self.assertLessEqual(int(r.headers["Retry-After"]), settings.OTP_RESEND_COOLDOWN_SECONDS)
        self.assertEqual(len(mailer.codes_for(email)), 1, "no email may be sent during the cooldown")

    def test_hourly_send_limit_is_enforced(self):
        email = fresh_email()
        with mock.patch.object(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0), \
             mock.patch.object(settings, "OTP_MAX_SENDS_PER_HOUR", 3):
            signup(email)                                            # send 1
            self.assertEqual(resend(email).status_code, 200)         # send 2
            self.assertEqual(resend(email).status_code, 200)         # send 3
            blocked = resend(email)
            self.assertEqual(blocked.status_code, 429)
            self.assertGreater(int(blocked.headers["Retry-After"]), 0)
        self.assertEqual(len(mailer.codes_for(email)), 3)

    def test_resend_for_unknown_or_verified_accounts_is_a_silent_noop(self):
        ghost = fresh_email("ghost")
        r = resend(ghost)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mailer.codes_for(ghost), [])

        email = fresh_email()
        signup(email)
        verify(email, mailer.last_code(email))
        sent_before = len(mailer.codes_for(email))
        with mock.patch.object(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0):
            again = resend(email)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json(), r.json())                     # indistinguishable from "unknown"
        self.assertEqual(len(mailer.codes_for(email)), sent_before)


class DuplicateSignupTests(OtpTestCase):
    def test_duplicate_of_a_pending_account_is_rejected_without_another_email(self):
        email = fresh_email()
        signup(email)
        again = signup(email, "some-other-password")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(len(mailer.codes_for(email)), 1)
        # The original password is untouched by the rejected duplicate.
        verify(email, mailer.last_code(email))
        self.assertEqual(login(email).status_code, 200)

    def test_duplicate_of_a_verified_account_is_rejected(self):
        email = fresh_email()
        signup(email)
        verify(email, mailer.last_code(email))
        self.assertEqual(signup(email, "attacker-password").status_code, 400)
        self.assertEqual(login(email, "attacker-password").status_code, 401)
        self.assertEqual(login(email).status_code, 200)

    def test_stale_unverified_account_can_be_reclaimed_by_a_new_signup(self):
        email = fresh_email()
        signup(email, "squatter-password-1")
        backdate_account(email, settings.UNVERIFIED_ACCOUNT_TTL_HOURS + 1)

        mine = signup(email, "real-owner-password")
        self.assertEqual(mine.status_code, 200, mine.text)
        self.assertEqual(len(mailer.codes_for(email)), 2)
        verify(email, mailer.last_code(email))
        self.assertEqual(login(email, "squatter-password-1").status_code, 401)
        self.assertEqual(login(email, "real-owner-password").status_code, 200)


class DeliveryProblemTests(OtpTestCase):
    def test_provider_failure_returns_503_leaves_account_unverified_and_allows_instant_retry(self):
        email = fresh_email()
        mailer.fail_next = True
        r = signup(email)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(mailer.codes_for(email), [])

        user, row = snapshot(email)
        self.assertFalse(user.is_verified)
        self.assertIsNone(row, "an unsent code must not be stored")
        self.assertEqual(login(email).status_code, 403)

        # No cooldown was started by the failed send.
        self.assertEqual(resend(email).status_code, 200)
        self.assertEqual(verify(email, mailer.last_code(email)).status_code, 200)

    def test_unconfigured_email_service_fails_before_creating_an_account(self):
        email = fresh_email()
        mailer.configured = False
        self.assertEqual(signup(email).status_code, 503)
        self.assertIsNone(snapshot(email)[0])
        self.assertEqual(resend(email).status_code, 503)

        mailer.configured = True
        self.assertEqual(signup(email).status_code, 200)

    def test_with_verification_disabled_signup_and_login_work_as_before(self):
        email = fresh_email()
        with mock.patch.object(settings, "EMAIL_VERIFICATION_REQUIRED", False):
            mailer.configured = False                                # no email service needed
            r = signup(email)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()["is_verified"])
            self.assertEqual(login(email).status_code, 200)
        self.assertEqual(mailer.codes_for(email), [])


class NothingLeaksTests(OtpTestCase):
    def test_codes_do_not_reach_logs_stdout_or_stderr(self):
        captured_logs = []

        class Collect(logging.Handler):
            def emit(self, record):
                captured_logs.append(record.getMessage())

        handler, root = Collect(level=logging.DEBUG), logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        out, err = io.StringIO(), io.StringIO()
        email, codes = fresh_email(), []
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                signup(email)
                codes.append(mailer.last_code(email))
                verify(email, wrong_code_for(codes[0]))
                mailer.fail_next = True
                with mock.patch.object(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0):
                    resend(email)                                    # failed delivery path
                    resend(email)
                    codes.append(mailer.last_code(email))
                verify(email, codes[-1])
        finally:
            root.removeHandler(handler)
            root.setLevel(previous_level)

        everything = "\n".join(captured_logs) + out.getvalue() + err.getvalue()
        for code in codes:
            self.assertNoCode(everything, code)


class SmtpSenderTests(unittest.TestCase):
    CONFIG = dict(
        SMTP_HOST="smtp.test.invalid", SMTP_PORT=587, SMTP_USERNAME="mail-user",
        SMTP_PASSWORD="mail-pass-not-real", EMAIL_FROM="no-reply@fitflow.test",
        EMAIL_FROM_NAME="FitFlow", SMTP_USE_SSL=False, SMTP_USE_STARTTLS=True, SMTP_TIMEOUT_SECONDS=10,
    )

    def send(self, **overrides):
        with mock.patch.multiple(settings, **{**self.CONFIG, **overrides}):
            return asyncio.run(SmtpEmailSender().send_verification_code("runner@example.com", "482913", 10))

    def test_is_configured_requires_a_host_and_a_valid_sender_address(self):
        cases = [
            (dict(), True),
            (dict(SMTP_HOST=None), False),
            (dict(SMTP_HOST=""), False),
            (dict(EMAIL_FROM=None), False),
            (dict(EMAIL_FROM="donotreplyfitflow.co.in"), False),      # no "@": not an address
            (dict(EMAIL_FROM="@fitflow.test"), False),
            (dict(EMAIL_FROM="Name <no-reply@fitflow.test>"), False),  # must be a bare address
        ]
        for overrides, expected in cases:
            with self.subTest(overrides=overrides), mock.patch.multiple(settings, **{**self.CONFIG, **overrides}):
                self.assertEqual(SmtpEmailSender().is_configured, expected)

    def test_default_settings_are_unconfigured(self):
        self.assertFalse(SmtpEmailSender().is_configured)            # the harness blanks every SMTP value

    def test_starttls_login_and_message_contents(self):
        with mock.patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            self.send()
        smtp_cls.assert_called_once_with("smtp.test.invalid", 587, timeout=10)
        server = smtp_cls.return_value
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("mail-user", "mail-pass-not-real")
        server.send_message.assert_called_once()

        message = server.send_message.call_args.args[0]
        self.assertEqual(message["To"], "runner@example.com")
        self.assertIn("no-reply@fitflow.test", message["From"])
        self.assertEqual(message["Subject"], "Your FitFlow verification code")
        body = message.get_body(("plain",)).get_content()
        self.assertIn("482913", body)
        self.assertIn("10 minutes", body)
        self.assertNotIn("mail-pass-not-real", message.as_string())  # credentials never go in the mail

    def test_implicit_tls_uses_smtp_ssl_and_skips_starttls(self):
        with mock.patch("app.services.email_service.smtplib.SMTP_SSL") as ssl_cls, \
             mock.patch("app.services.email_service.smtplib.SMTP") as plain_cls:
            self.send(SMTP_USE_SSL=True, SMTP_PORT=465)
        plain_cls.assert_not_called()
        ssl_cls.return_value.starttls.assert_not_called()
        ssl_cls.return_value.send_message.assert_called_once()

    def test_provider_errors_become_a_detail_free_delivery_error(self):
        with mock.patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials 482913")
            with self.assertLogs("app.services.email_service", level="WARNING") as logs:
                with self.assertRaises(EmailDeliveryError) as ctx:
                    self.send()
        self.assertEqual(ctx.exception.args, ())
        self.assertTrue(ctx.exception.__suppress_context__)
        self.assertEqual(smtp_cls.return_value.send_message.call_count, 0)
        joined = "\n".join(logs.output)
        self.assertIn("SMTPAuthenticationError", joined)
        self.assertNotIn("482913", joined)
        self.assertNotIn("runner@example.com", joined)

    def test_network_errors_are_wrapped_too(self):
        with mock.patch("app.services.email_service.smtplib.SMTP", side_effect=TimeoutError("timed out")):
            with self.assertLogs("app.services.email_service", level="WARNING"):
                with self.assertRaises(EmailDeliveryError):
                    self.send()

    def test_no_silent_fallback_to_plaintext_when_starttls_is_unavailable(self):
        with mock.patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.starttls.side_effect = smtplib.SMTPNotSupportedError("no STARTTLS")
            with self.assertLogs("app.services.email_service", level="WARNING"):
                with self.assertRaises(EmailDeliveryError):
                    self.send()
        smtp_cls.return_value.login.assert_not_called()
        smtp_cls.return_value.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
