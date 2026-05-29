"""
Transcription Service — Groq Whisper + AssemblyAI Speaker Diarization
======================================================================

Strategy:
  - If ASSEMBLYAI_API_KEY is set in .env → use AssemblyAI
    • Single API call returns transcript + speaker labels + word timestamps
    • Output format: "[Speaker A 00:00:05] Hello everyone..."
    • Free tier: 5 hours/month

  - If no AssemblyAI key → fall back to Groq Whisper (plain text, no speakers)

Why AssemblyAI over pyannote?
  - No local GPU/CUDA needed (works on any Windows laptop)
  - Better accuracy on real-world meeting audio
  - Single API call vs running two separate models and aligning them
  - Industry-grade diarization with speaker labels

Why keep Groq as fallback?
  - Zero cost, already configured
  - Works for quick testing without a second API key
  - If AssemblyAI key expires, pipeline doesn't break
"""
import logging
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# AssemblyAI Transcription (with diarization)
# ─────────────────────────────────────────────

def _transcribe_with_assemblyai(audio_path: str) -> str:
    """
    Transcribe audio using AssemblyAI with speaker diarization enabled.

    Returns a formatted transcript like:
        [Speaker A 00:00:05] Hello everyone, thanks for joining.
        [Speaker B 00:00:11] Sure, let's start with the agenda.

    AssemblyAI automatically detects how many speakers are present
    and assigns labels (Speaker A, Speaker B, ...).
    """
    import assemblyai as aai

    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

    config = aai.TranscriptionConfig(
        speaker_labels=True,           # Enable diarization
        speakers_expected=None,        # Auto-detect number of speakers
        language_code="en",
        punctuate=True,
        format_text=True,
    )

    logger.info(f"Uploading to AssemblyAI for diarization: {audio_path}")
    transcriber = aai.Transcriber()
    transcript_obj = transcriber.transcribe(audio_path, config=config)

    if transcript_obj.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {transcript_obj.error}")

    # Build formatted transcript with speaker labels and timestamps
    lines = []
    for utterance in transcript_obj.utterances:
        # Convert milliseconds to MM:SS
        start_ms = utterance.start
        minutes = int(start_ms // 60000)
        seconds = int((start_ms % 60000) // 1000)
        timestamp = f"{minutes:02d}:{seconds:02d}"

        speaker = f"Speaker {utterance.speaker}"
        lines.append(f"[{speaker} {timestamp}] {utterance.text}")

    result = "\n".join(lines)
    logger.info(f"AssemblyAI diarization complete — {len(lines)} utterances")
    return result


# ─────────────────────────────────────────────
# Groq Whisper Transcription (fallback, no speakers)
# ─────────────────────────────────────────────

def _transcribe_with_groq(audio_path: str) -> str:
    """
    Transcribe audio using Groq Whisper API (plain text, no speaker labels).
    Used as fallback when AssemblyAI key is not configured.
    """
    from groq import Groq

    client = Groq(api_key=settings.GROQ_API_KEY)
    file_path = Path(audio_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info(f"Transcribing with Groq Whisper (no diarization): {audio_path}")

    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(file_path.name, audio_file.read()),
            model=settings.GROQ_WHISPER_MODEL,
            response_format="text",
            language="en",
            temperature=0.0,
        )

    result = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
    logger.info("Groq Whisper transcription complete")
    return result


# ─────────────────────────────────────────────
# Public API — smart router
# ─────────────────────────────────────────────

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio with the best available method.

    Priority:
      1. AssemblyAI (if ASSEMBLYAI_API_KEY is set) → speakers + timestamps
      2. Groq Whisper (fallback)                   → plain text

    Args:
        audio_path: Absolute path to the audio file on disk.

    Returns:
        Transcript string.
        - With AssemblyAI: "[Speaker A 00:00:05] text..."
        - With Groq: plain text paragraph

    Raises:
        Exception: If both methods fail.
    """
    file_path = Path(audio_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Use AssemblyAI if key is available
    if settings.ASSEMBLYAI_API_KEY:
        try:
            return _transcribe_with_assemblyai(audio_path)
        except Exception as e:
            logger.warning(f"AssemblyAI failed ({e}), falling back to Groq Whisper...")

    # Fallback to Groq Whisper
    return _transcribe_with_groq(audio_path)
