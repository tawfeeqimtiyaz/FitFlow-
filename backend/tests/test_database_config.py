import os
import subprocess
import sys
import unittest

from tests.support import BACKEND_DIR

from sqlalchemy.engine import make_url

from app.config import Settings, settings
from app.database import engine
from app.services.food_ai_service import FoodAIService


def make_settings(url: str, **extra) -> Settings:
    return Settings(_env_file=None, DATABASE_URL=url, SECRET_KEY="x", **extra)


class AsyncUrlTests(unittest.TestCase):
    def test_render_style_postgres_scheme_is_normalised(self):
        s = make_settings("postgres://u:p@db.example.com:5432/fit")
        self.assertEqual(s.ASYNC_DATABASE_URL, "postgresql+asyncpg://u:p@db.example.com:5432/fit")

    def test_plain_postgresql_scheme_is_normalised(self):
        s = make_settings("postgresql://u:p@db.example.com/fit")
        self.assertEqual(s.ASYNC_DATABASE_URL, "postgresql+asyncpg://u:p@db.example.com/fit")

    def test_asyncpg_and_sqlite_urls_are_left_alone(self):
        for url in ("postgresql+asyncpg://u:p@h/db", "sqlite+aiosqlite:///./x.db"):
            with self.subTest(url=url):
                self.assertEqual(make_settings(url).ASYNC_DATABASE_URL, url)


class EngineUsesConfiguredUrlTests(unittest.TestCase):
    def test_engine_matches_settings(self):
        self.assertEqual(engine.url, make_url(settings.ASYNC_DATABASE_URL))
        self.assertEqual(engine.url.drivername, "sqlite+aiosqlite")

    def test_debug_mode_no_longer_swaps_a_remote_url_for_local_sqlite(self):
        # Regression: DEBUG=True used to replace any *supabase.com* URL with
        # the local SQLite file, silently ignoring the configured database.
        # Engine creation does not connect, so this is safe to run offline.
        code = "from app.database import engine; print(engine.url.drivername, engine.url.host)"
        env = {
            **os.environ,
            "DATABASE_URL": "postgres://u:p@db.example.supabase.com:5432/postgres",
            "DEBUG": "True",
        }
        out = subprocess.run(
            [sys.executable, "-W", "ignore", "-c", code],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "postgresql+asyncpg db.example.supabase.com")


class GeminiModelConfigTests(unittest.TestCase):
    def test_model_is_configurable_and_not_the_retired_default(self):
        self.assertNotEqual(make_settings("sqlite+aiosqlite:///x.db").GEMINI_MODEL, "gemini-1.5-flash")
        custom = make_settings("sqlite+aiosqlite:///x.db", GEMINI_MODEL="gemini-custom")
        self.assertEqual(custom.GEMINI_MODEL, "gemini-custom")

    def test_nutrition_url_uses_the_configured_model(self):
        self.assertTrue(
            FoodAIService.GEMINI_API_URL.endswith(f"models/{settings.GEMINI_MODEL}:generateContent")
        )
        self.assertNotIn("1.5", FoodAIService.GEMINI_API_URL)


if __name__ == "__main__":
    unittest.main()
