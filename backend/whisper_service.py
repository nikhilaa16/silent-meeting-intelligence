"""
Transcription service using Groq's Whisper API.

Why Groq's Whisper instead of running Whisper locally?
- No GPU/CUDA setup required → works on any Windows machine
- 10–50x faster than running locally on CPU
- Free tier is more than enough for our use case
- Same model (whisper-large-v3-turbo), same accuracy
"""
from pathlib import Path

from groq import Groq

from .config import settings


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio/video file using Groq's Whisper API.

    Args:
        audio_path: Absolute path to the audio file on disk.

    Returns:
        Full transcript as a plain string.

    Raises:
        Exception: If transcription fails (API error, file not found, etc.)
    """
    client = Groq(api_key=settings.GROQ_API_KEY)
    file_path = Path(audio_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(file_path.name, audio_file.read()),
            model=settings.GROQ_WHISPER_MODEL,
            response_format="text",
            language="en",          # Force English for faster processing
            temperature=0.0,        # Deterministic output
        )

    # Groq returns the text directly when response_format="text"
    return transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
