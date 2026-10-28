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

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {
        "env_file": BASE_DIR / ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()