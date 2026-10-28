"""Shared test harness.

Importing this module points the app at a throwaway SQLite file, blanks the AI
keys and SMTP settings, and swaps the mail provider for an in-memory fake, so
tests never touch backend/fitflow.db, a real database, the network, or a real
mailbox. It must be imported before anything from `app`.
"""
import atexit
import os
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = tempfile.mkdtemp(prefix="fitflow-test-")

# Plain assignment (not setdefault): environment variables beat backend/.env.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_TMP_DIR, 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DEBUG"] = "False"
os.environ["GEMINI_API_KEY"] = ""
os.environ["CLARIFAI_PAT"] = ""
os.environ["EMAIL_VERIFICATION_REQUIRED"] = "True"
for _name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM"):
    os.environ[_name] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402

# Safety net: refuse to run against anything but the temp database.
assert "fitflow-test-" in settings.DATABASE_URL, "tests must use the temp database"

from app.main import app  # noqa: E402
from app.services.email_service import EmailDeliveryError, EmailSender, get_email_sender  # noqa: E402


class FakeEmailSender(EmailSender):
    """Records messages instead of sending them. This is the only place a test
    can read a verification code, mirroring the real inbox."""

    def __init__(self):
        self.configured = True
        self.fail_next = False
        self.sent = []          # list of (to_email, code)

    @property
    def is_configured(self) -> bool:
        return self.configured

    async def send_verification_code(self, to_email, code, expires_minutes):
        if self.fail_next:
            self.fail_next = False
            raise EmailDeliveryError()
        self.sent.append((to_email, code))

    def codes_for(self, email):
        return [code for to, code in self.sent if to == email]

    def last_code(self, email):
        codes = self.codes_for(email)
        assert codes, f"no verification email was sent to {email}"
        return codes[-1]

    def reset(self):
        self.configured, self.fail_next = True, False


mailer = FakeEmailSender()
app.dependency_overrides[get_email_sender] = lambda: mailer

# One client (and one event loop) for the whole run; the async engine is
# bound to that loop, so every test module shares it.
client = TestClient(app)
client.__enter__()
atexit.register(lambda: client.__exit__(None, None, None))


def run_async(func, *args):
    """Run an async callable on the app's own event loop (e.g. to seed rows)."""
    return client.portal.call(func, *args)


def new_user(prefix: str = "user") -> SimpleNamespace:
    """Sign up, verify the emailed code, and log in a fresh user."""
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    password = "correct-horse-battery"

    signup = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 200, signup.text

    verify = client.post("/api/auth/verify-otp", json={"email": email, "otp": mailer.last_code(email)})
    assert verify.status_code == 200, verify.text

    login = client.post("/api/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text

    return SimpleNamespace(
        id=signup.json()["id"],
        email=email,
        password=password,
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
