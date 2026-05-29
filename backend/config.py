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
    GROQ_LLM_MODEL: str = "llama-3.1-8b-instant"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"

    # Storage
    UPLOAD_DIR: Path = Path("uploads")
    DB_PATH: str = "meetings.db"
    MAX_FILE_SIZE_MB: int = 100

    # Authentication
    # Set a strong secret key here. Dashboard will use this to talk to the API.
    # Generate one: python -c "import secrets; print(secrets.token_hex(32))"
    API_KEY: str = "change-me-to-a-strong-secret-key"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
