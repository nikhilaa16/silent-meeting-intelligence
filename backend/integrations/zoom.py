"""
Zoom Integration
=================

Uses Zoom Server-to-Server OAuth (recommended for internal tools — no user login needed).
Fetches cloud recordings from the Zoom API and downloads them for processing.

Setup (one-time, 5 minutes):
  1. Go to https://marketplace.zoom.us/develop/create
  2. Create a "Server-to-Server OAuth" app
  3. Add scope: cloud_recording:read:list_account_recordings
  4. Get your Account ID, Client ID, and Client Secret
  5. Add to .env:
       ZOOM_ACCOUNT_ID=your_account_id
       ZOOM_CLIENT_ID=your_client_id
       ZOOM_CLIENT_SECRET=your_client_secret

API Flow:
  POST https://zoom.us/oauth/token  (get access token)
      ↓
  GET  /v2/accounts/me/recordings   (list all cloud recordings)
      ↓
  GET  recording.download_url       (download the audio/video file)
      ↓
  POST /meetings/upload             (push into SMI pipeline)
"""
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from ..config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Zoom OAuth Token Manager
# ─────────────────────────────────────────────

_zoom_token_cache: dict = {"token": None, "expires_at": 0}


def _get_zoom_access_token() -> str:
    """
    Get a Zoom Server-to-Server OAuth access token.
    Tokens expire in 1 hour — cached and auto-refreshed.

    Returns:
        Bearer token string for Authorization header.

    Raises:
        RuntimeError: If Zoom credentials are not configured.
    """
    if not all([settings.ZOOM_ACCOUNT_ID, settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET]):
        raise RuntimeError(
            "Zoom credentials not configured. Set ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, "
            "and ZOOM_CLIENT_SECRET in your .env file."
        )

    # Return cached token if still valid (with 60s buffer)
    if _zoom_token_cache["token"] and time.time() < _zoom_token_cache["expires_at"] - 60:
        return _zoom_token_cache["token"]

    # Request a new token
    response = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "account_credentials",
            "account_id": settings.ZOOM_ACCOUNT_ID,
        },
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Zoom OAuth failed: {response.status_code} — {response.text[:200]}")

    data = response.json()
    _zoom_token_cache["token"] = data["access_token"]
    _zoom_token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

    logger.info("Zoom access token refreshed successfully")
    return _zoom_token_cache["token"]


# ─────────────────────────────────────────────
# Zoom Recording Fetcher
# ─────────────────────────────────────────────

def list_zoom_recordings(days_back: int = 30, page_size: int = 20) -> list[dict]:
    """
    Fetch cloud recordings from the last N days via Zoom API v2.

    Args:
        days_back:  How many days back to search for recordings.
        page_size:  Max number of recordings to return per call (max 300).

    Returns:
        List of recording dicts with keys:
          - id, topic, start_time, duration, download_url, file_type, file_size
    """
    token = _get_zoom_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = datetime.utcnow().strftime("%Y-%m-%d")

    response = requests.get(
        "https://api.zoom.us/v2/accounts/me/recordings",
        headers=headers,
        params={
            "from": from_date,
            "to": to_date,
            "page_size": page_size,
        },
        timeout=15,
    )

    if response.status_code == 404:
        # Account-level endpoint might not be available on all Zoom plans
        # Fall back to user-level endpoint
        response = requests.get(
            "https://api.zoom.us/v2/users/me/recordings",
            headers=headers,
            params={"from": from_date, "to": to_date, "page_size": page_size},
            timeout=15,
        )

    if response.status_code != 200:
        raise RuntimeError(f"Zoom API error: {response.status_code} — {response.text[:300]}")

    data = response.json()
    meetings = data.get("meetings", [])

    recordings = []
    for meeting in meetings:
        for rec_file in meeting.get("recording_files", []):
            # Only include audio/video files (skip chat logs, transcripts, etc.)
            if rec_file.get("file_type") in ("MP4", "M4A", "audio/m4a"):
                recordings.append({
                    "id": rec_file.get("id"),
                    "meeting_id": meeting.get("id"),
                    "topic": meeting.get("topic", "Untitled Meeting"),
                    "start_time": meeting.get("start_time"),
                    "duration_minutes": meeting.get("duration", 0),
                    "download_url": rec_file.get("download_url"),
                    "file_type": rec_file.get("file_type"),
                    "file_size_mb": round(rec_file.get("file_size", 0) / (1024 * 1024), 1),
                    "platform": "zoom",
                })

    logger.info(f"Found {len(recordings)} Zoom recordings in the last {days_back} days")
    return recordings


def download_zoom_recording(download_url: str, filename: str, upload_dir: str) -> str:
    """
    Download a Zoom cloud recording to the uploads directory.

    Args:
        download_url: Zoom recording download URL (from list_zoom_recordings).
        filename:     Desired filename for the saved file.
        upload_dir:   Directory to save the file.

    Returns:
        Absolute path to the downloaded file.
    """
    token = _get_zoom_access_token()

    logger.info(f"Downloading Zoom recording: {filename}")
    response = requests.get(
        download_url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=300,  # Large files can take time
    )

    if response.status_code != 200:
        raise RuntimeError(f"Failed to download Zoom recording: {response.status_code}")

    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    logger.info(f"Zoom recording downloaded: {file_path} ({size_mb:.1f} MB)")
    return file_path
