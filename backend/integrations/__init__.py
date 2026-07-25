"""
Meeting Platform Integrations
==============================
Zoom, Google Meet, and Microsoft Teams

Each integration follows the same pattern:
  1. OAuth / API Key authentication with the platform
  2. Fetch list of recorded meetings from the platform's API
  3. Download the audio/video recording
  4. Pipe it through the existing SMI transcription + intelligence pipeline

Why this matters:
  Without integrations, users must manually download recordings and upload them.
  With integrations, SMI can pull recordings automatically — making it a
  genuinely passive, hands-free meeting intelligence system.
"""
