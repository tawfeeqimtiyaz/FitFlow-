import unittest
from unittest import mock

from tests.support import client, new_user

from app.config import settings
from app.services import ai_service


def chat(user, message, context=None):
    body = {"message": message}
    if context:
        body["context"] = context
    r = client.post("/api/medical/chat", headers=user.headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


class KeywordFallbackTests(unittest.TestCase):
    """The test harness blanks GEMINI_API_KEY, so these exercise the offline path."""

    @classmethod
    def setUpClass(cls):
        cls.user = new_user("chat")

    def test_chat_requires_auth(self):
        self.assertEqual(client.post("/api/medical/chat", json={"message": "hi"}).status_code, 401)

    def test_greeting_starts_symptom_flow(self):
        body = chat(self.user, "hello there")
        self.assertEqual(body["context"], "symptom")
        self.assertIn("Medical Assistant", body["reply"])

    def test_knee_pain_suggests_orthopedic_specialist(self):
        body = chat(self.user, "my knee hurts when I run")
        self.assertEqual(body["suggestions"][0]["doctor_type"], "Orthopedic Specialist")
        self.assertEqual(body["suggestions"][0]["urgency"], "medium")
        self.assertEqual(body["context"], "diagnosis")

    def test_chest_tightness_is_high_urgency(self):
        body = chat(self.user, "I feel chest tightness during cardio")
        self.assertEqual(body["suggestions"][0]["doctor_type"], "Cardiologist")
        self.assertEqual(body["suggestions"][0]["urgency"], "high")

    def test_diagnosis_context_returns_exercise_tips(self):
        body = chat(self.user, "knee ligament sprain", context="diagnosis")
        tips = body["exercise_tips"]
        self.assertTrue(tips["avoid"])
        self.assertTrue(tips["recommended"])
        self.assertTrue(tips["tips"])
        self.assertEqual(body["context"], "tips")

    def test_unrecognised_message_asks_for_detail(self):
        body = chat(self.user, "zzz qqq")
        self.assertIsNone(body["suggestions"])
        self.assertIn("more detail", body["reply"])


class GeminiFailureFallbackTests(unittest.TestCase):
    """With a key configured, a Gemini failure must degrade to the keyword bot."""

    @classmethod
    def setUpClass(cls):
        cls.user = new_user("chat-gem")

    def test_gemini_error_falls_back_and_uses_configured_model(self):
        fake_genai = mock.MagicMock()
        fake_genai.GenerativeModel.side_effect = RuntimeError("simulated Gemini outage")

        with mock.patch.object(settings, "GEMINI_API_KEY", "fake-key"), \
             mock.patch.object(ai_service, "genai", fake_genai):
            body = chat(self.user, "my knee hurts")

        _, kwargs = fake_genai.GenerativeModel.call_args
        self.assertEqual(kwargs["model_name"], settings.GEMINI_MODEL)
        self.assertEqual(body["suggestions"][0]["doctor_type"], "Orthopedic Specialist")

    def test_missing_sdk_falls_back_even_with_a_key(self):
        with mock.patch.object(settings, "GEMINI_API_KEY", "fake-key"), \
             mock.patch.object(ai_service, "genai", None):
            body = chat(self.user, "my lower back hurts")
        self.assertEqual(body["suggestions"][0]["doctor_type"], "Physiotherapist")


if __name__ == "__main__":
    unittest.main()
