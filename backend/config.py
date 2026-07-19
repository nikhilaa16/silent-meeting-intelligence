"""
Configuration management using pydantic-settings.
All settings are loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Groq API (transcription fallback + LLM for all intelligence nodes)
    GROQ_API_KEY: str = ""

    # AssemblyAI API (primary transcription with speaker diarization)
    # Get a free key at: https://www.assemblyai.com/
    # Free tier: 5 hours/month — plenty for a FYP demo
    # Leave blank to fall back to Groq Whisper (no speaker labels)
    ASSEMBLYAI_API_KEY: str = ""

    # Model names
    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"

    # Storage
    UPLOAD_DIR: Path = Path("uploads")
    DB_PATH: str = "meetings.db"
    MAX_FILE_SIZE_MB: int = 100

    # ── Database ─────────────────────────────────────────────────────────
    # Set DATABASE_URL to switch to PostgreSQL for production:
    #   postgresql+psycopg2://user:password@host:5432/dbname
    # Leave blank to use SQLite (default for local dev/demo).
    DATABASE_URL: str = ""

    # ── Multi-Language Support ────────────────────────────────────────────
    # Default transcription language.
    # "auto" lets Whisper auto-detect. Or use ISO codes: en, hi, ta, fr, de, es, ja, zh, ar
    DEFAULT_LANGUAGE: str = "auto"

    # ── JWT Authentication ────────────────────────────────────────────────
    # Secret key for signing JWT tokens. Generate with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str = "silent-meeting-jwt-super-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Legacy API Key (kept for backward compat with Streamlit dashboard)
    API_KEY: str = "silent-meeting-super-secret-2025"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
