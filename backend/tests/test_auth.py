import unittest
import uuid
from datetime import timedelta

from tests.support import client, new_user, run_async

from app.database import AsyncSessionLocal
from app.models.user import User
from app.utils.security import create_access_token


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class SignupAndLoginTests(unittest.TestCase):
    def test_signup_returns_uuid_id_and_no_password(self):
        user = new_user("signup")
        uuid.UUID(user.id)  # raises if the id is not a UUID
        me = client.get("/api/users/me", headers=user.headers).json()
        self.assertEqual(me["email"], user.email)
        self.assertNotIn("hashed_password", me)
        self.assertNotIn("password", me)

    def test_duplicate_email_is_rejected(self):
        user = new_user("dup")
        again = client.post(
            "/api/auth/signup", json={"email": user.email, "password": "another-password"}
        )
        self.assertEqual(again.status_code, 400)

    def test_invalid_email_is_rejected(self):
        r = client.post("/api/auth/signup", json={"email": "not-an-email", "password": "x" * 10})
        self.assertEqual(r.status_code, 422)

    def test_form_login_and_json_login_both_work(self):
        user = new_user("login")
        form = client.post(
            "/api/auth/login", data={"username": user.email, "password": user.password}
        )
        as_json = client.post(
            "/api/auth/login/json", json={"email": user.email, "password": user.password}
        )
        self.assertEqual(form.status_code, 200)
        self.assertEqual(as_json.status_code, 200)
        self.assertEqual(as_json.json()["token_type"], "bearer")

    def test_wrong_password_and_unknown_email_are_401(self):
        user = new_user("badpw")
        wrong = client.post(
            "/api/auth/login", data={"username": user.email, "password": "nope-nope-nope"}
        )
        unknown = client.post(
            "/api/auth/login", data={"username": "ghost@example.com", "password": "whatever-1"}
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)

    def test_usernames_are_unique_for_same_email_prefix(self):
        a = client.post("/api/auth/signup", json={"email": "same@one.example", "password": "pw-pw-pw-pw"})
        b = client.post("/api/auth/signup", json={"email": "same@two.example", "password": "pw-pw-pw-pw"})
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)


class ProtectedEndpointTests(unittest.TestCase):
    PROTECTED = [
        ("get", "/api/users/me"),
        ("get", "/api/users/me/profile"),
        ("get", "/api/calorie/balance"),
        ("get", "/api/calorie/progress"),
        ("get", "/api/medical/symptoms"),
        ("get", "/api/mindfulness/stats"),
        ("get", "/api/workouts/history"),
        ("post", "/api/medical/chat"),
    ]

    def test_no_token_is_rejected_everywhere(self):
        for method, path in self.PROTECTED:
            with self.subTest(path=path):
                r = getattr(client, method)(path)
                self.assertEqual(r.status_code, 401)

    def test_garbage_token_is_rejected(self):
        self.assertEqual(client.get("/api/users/me", headers=bearer("not.a.jwt")).status_code, 401)

    def test_valid_token_is_accepted(self):
        user = new_user("valid")
        self.assertEqual(client.get("/api/users/me", headers=user.headers).status_code, 200)

    def test_token_with_non_uuid_subject_is_rejected(self):
        # Regression: get_current_user once int()-parsed the subject, which
        # made every valid UUID token fail and accepted integer-style ones.
        token = create_access_token({"sub": "12345"})
        self.assertEqual(client.get("/api/users/me", headers=bearer(token)).status_code, 401)

    def test_token_without_subject_is_rejected(self):
        token = create_access_token({"foo": "bar"})
        self.assertEqual(client.get("/api/users/me", headers=bearer(token)).status_code, 401)

    def test_token_for_unknown_user_is_rejected(self):
        token = create_access_token({"sub": str(uuid.uuid4())})
        self.assertEqual(client.get("/api/users/me", headers=bearer(token)).status_code, 401)

    def test_expired_token_is_rejected(self):
        user = new_user("expired")
        token = create_access_token({"sub": user.id}, expires_delta=timedelta(seconds=-5))
        self.assertEqual(client.get("/api/users/me", headers=bearer(token)).status_code, 401)

    def test_inactive_user_is_rejected(self):
        user = new_user("inactive")

        async def deactivate():
            async with AsyncSessionLocal() as db:
                row = await db.get(User, uuid.UUID(user.id))
                row.is_active = False
                await db.commit()

        run_async(deactivate)
        self.assertEqual(client.get("/api/users/me", headers=user.headers).status_code, 400)


if __name__ == "__main__":
    unittest.main()
