from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "FitFlow"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Convert DATABASE_URL to async-compatible format.
        Render gives postgres:// but SQLAlchemy needs postgresql+asyncpg://
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # JWT Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Clarifai API (food image detection)
    CLARIFAI_PAT: Optional[str] = None

    # Nutritionix API — REPLACED BY GEMINI
    NUTRITIONIX_APP_ID: Optional[str] = None   # ✅ keep for backward compat
    NUTRITIONIX_APP_KEY: Optional[str] = None  # ✅ keep for backward compat

    # ✅ ADDED: Gemini API
    GEMINI_API_KEY: Optional[str] = None
    # Override via env when Google retires or replaces the model.
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Email verification (OTP) ──────────────────────────────────────────
    # When True, new accounts must confirm a one-time code emailed to them
    # before they can log in. Set False only for local development without SMTP.
    EMAIL_VERIFICATION_REQUIRED: bool = True

    # SMTP provider. Nothing here has a usable default on purpose: delivery is
    # reported as "not configured" until the host and a valid sender are set.
    EMAIL_FROM: Optional[str] = None            # e.g. no-reply@your-domain.tld
    EMAIL_FROM_NAME: str = "FitFlow"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_SSL: bool = False                  # implicit TLS (usually port 465)
    SMTP_USE_STARTTLS: bool = True              # explicit TLS (usually port 587)
    SMTP_TIMEOUT_SECONDS: int = 10

    # OTP policy
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5                   # wrong guesses before the code is locked
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_SENDS_PER_HOUR: int = 5
    # An unverified signup older than this may be re-claimed by a new signup,
    # so nobody can squat on someone else's email address forever.
    UNVERIFIED_ACCOUNT_TTL_HOURS: int = 24

    model_config = {
        "env_file": BASE_DIR / ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()