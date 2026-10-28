"""Run the REAL API for end-to-end tests, with a mock email provider.

    cd backend && ../venv/Scripts/python tests/e2e_server.py --port 8765

It uses a throwaway SQLite database, blank AI/SMTP settings, and an in-memory
mailbox instead of SMTP, so no real email is ever sent. To let a test runner
read the "emailed" code it also exposes GET /__test__/codes?email=... .

TEST TOOLING ONLY: that route returns verification codes, so it is added here,
never in app/, and the server binds to 127.0.0.1 only. Not collected by
`unittest discover` (the file name does not start with "test").
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = tempfile.mkdtemp(prefix="fitflow-e2e-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_TMP_DIR, 'e2e.db').as_posix()}"
os.environ["SECRET_KEY"] = "e2e-secret-key-not-for-production"
os.environ["DEBUG"] = "False"
os.environ["EMAIL_VERIFICATION_REQUIRED"] = "True"
for _name in ("GEMINI_API_KEY", "CLARIFAI_PAT", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM"):
    os.environ[_name] = ""

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402
from app.services.email_service import EmailSender, get_email_sender  # noqa: E402


class MockMailbox(EmailSender):
    def __init__(self):
        self.sent = []  # (to_email, code)

    @property
    def is_configured(self) -> bool:
        return True

    async def send_verification_code(self, to_email, code, expires_minutes):
        self.sent.append((to_email, code))


mailbox = MockMailbox()
app.dependency_overrides[get_email_sender] = lambda: mailbox


@app.get("/__test__/codes")
async def codes_for(email: str):
    return {"codes": [code for to, code in mailbox.sent if to == email]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
