"""
Bhasha Shiksha Setu — Configuration
------------------------------------
All configuration comes from environment variables / the .env file.
Never hardcode secrets in this project.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = parent of the backend/ folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from the .env file at the project root (if present)
load_dotenv(BASE_DIR / ".env")


def _bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # ---------- Core ----------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    DEBUG = _bool(os.getenv("DEBUG"), False)

    # SQLite by default; set DATABASE_URL=postgresql://... for production
    _default_db = "sqlite:///" + str(BASE_DIR / "bhasha_shiksha_setu.db")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", _default_db)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # ---------- Auth ----------
    JWT_EXPIRY_HOURS = int(os.getenv("TOKEN_EXPIRY_HOURS", "24"))
    LOGIN_MAX_ATTEMPTS = 5            # failed logins allowed before lockout
    LOGIN_LOCKOUT_MINUTES = 15        # lockout window

    # ---------- Security ----------
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "backend" / "uploads"))
    # Comma separated origins: e.g. https://site.com,https://admin.site.com
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # ---------- AI / Translation providers (keys ONLY in .env) ----------
    AI_PROVIDER = os.getenv("AI_PROVIDER", "demo")      # demo | openai
    AI_API_KEY = os.getenv("AI_API_KEY", "")            # never exposed to frontend
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")

    TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "demo")  # demo | openai
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "browser")               # browser | external

    # ---------- Static folders ----------
    FRONTEND_DIR = BASE_DIR / "frontend"
    ADMIN_DIR = BASE_DIR / "admin"

    # ---------- Default admin (used by create_admin.py / seed) ----------
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrator")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@bhasha.setu")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")

    # Seed demo accounts + sample lessons (handy for the SIH demo)
    SEED_DEMO = _bool(os.getenv("SEED_DEMO"), True)

    @staticmethod
    def public_settings():
        """Settings that are safe to expose to non-admin users (never secrets)."""
        return {
            "ai_provider": os.getenv("AI_PROVIDER", "demo"),
            "ai_model": os.getenv("AI_MODEL", "gpt-4o-mini"),
            "translation_provider": os.getenv("TRANSLATION_PROVIDER", "demo"),
        }
