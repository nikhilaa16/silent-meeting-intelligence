"""
Google Meet Integration
========================

Google Meet does NOT store recordings itself — recordings are automatically
saved to the host's Google Drive as MP4 files after the meeting ends.

This integration:
  1. Uses Google OAuth 2.0 (Service Account for server-to-server, or user OAuth)
  2. Searches Google Drive for Meet recording files
  3. Downloads the MP4 and pipes it through the SMI pipeline

Setup (one-time, 10 minutes):
  1. Go to https://console.cloud.google.com
  2. Create a project → Enable "Google Drive API"
  3. Create a Service Account → Download JSON key file
  4. Share your Google Drive "Meet Recordings" folder with the service account email
  5. Add to .env:
       GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account-key.json
       # OR use the JSON content directly:
       GOOGLE_SERVICE_ACCOUNT_INFO={"type":"service_account","project_id":...}

  Alternative — User OAuth (simpler for personal use):
       GOOGLE_CLIENT_ID=your_oauth_client_id
       GOOGLE_CLIENT_SECRET=your_oauth_client_secret

How Meet recordings appear in Drive:
  - Folder: "Meet Recordings" in Drive root
  - File name format: "Meeting title (YYYY-MM-DD at HH-MM-SS).mp4"
  - File type: video/mp4
"""
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional

import requests

from ..config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Google Drive OAuth Token (Service Account)
# ─────────────────────────────────────────────

def _get_google_access_token() -> str:
    """
    Get a Google API access token using Service Account credentials (JWT flow).

    The service account JWT is signed locally and exchanged for an access token.
    This is the recommended method for server-to-server integrations.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If Google credentials are not configured.
    """
    if not settings.GOOGLE_SERVICE_ACCOUNT_INFO:
        raise RuntimeError(
            "Google credentials not configured. Set GOOGLE_SERVICE_ACCOUNT_INFO "
            "in your .env file with your service account JSON content."
        )

    try:
        import google.auth
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request

        # Parse service account JSON (can be file path or raw JSON string)
        sa_info = settings.GOOGLE_SERVICE_ACCOUNT_INFO
        if os.path.isfile(sa_info):
            with open(sa_info) as f:
                sa_dict = json.load(f)
        else:
            sa_dict = json.loads(sa_info)

        credentials = service_account.Credentials.from_service_account_info(
            sa_dict,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        credentials.refresh(Request())
        return credentials.token

    except ImportError:
        raise RuntimeError(
            "google-auth package not installed. Run: pip install google-auth google-auth-httplib2"
        )


# ─────────────────────────────────────────────
# Google Meet Recording Fetcher (via Google Drive)
# ─────────────────────────────────────────────

def list_google_meet_recordings(days_back: int = 30, max_results: int = 20) -> list[dict]:
    """
    Search Google Drive for Meet recordings from the last N days.

    Meet recordings are automatically saved to Drive with:
      - mimeType: video/mp4
      - name containing "Meet" OR parent folder named "Meet Recordings"

    Args:
        days_back:   How many days back to search.
        max_results: Maximum number of files to return.

    Returns:
        List of recording dicts with keys:
          - id, name, created_time, size_mb, download_url, platform
    """
    token = _get_google_access_token()

    # Build Drive API query for Meet recordings
    cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
    query = (
        f"mimeType='video/mp4' "
        f"and createdTime > '{cutoff_date}' "
        f"and (name contains 'Meet' or name contains 'meet' or 'Meet Recordings' in parents) "
        f"and trashed = false"
    )

    response = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": query,
            "fields": "files(id,name,createdTime,size,webContentLink)",
            "pageSize": max_results,
            "orderBy": "createdTime desc",
        },
        timeout=15,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Google Drive API error: {response.status_code} — {response.text[:300]}")

    files = response.json().get("files", [])

    recordings = []
    for f in files:
        size_bytes = int(f.get("size", 0))
        recordings.append({
            "id": f["id"],
            "name": f.get("name", "Google Meet Recording"),
            "topic": f.get("name", "Google Meet Recording").replace(".mp4", ""),
            "start_time": f.get("createdTime"),
            "file_size_mb": round(size_bytes / (1024 * 1024), 1),
            "download_url": f"https://www.googleapis.com/drive/v3/files/{f['id']}?alt=media",
            "file_type": "MP4",
            "platform": "google_meet",
        })

    logger.info(f"Found {len(recordings)} Google Meet recordings in Drive (last {days_back} days)")
    return recordings


def download_google_meet_recording(file_id: str, filename: str, upload_dir: str) -> str:
    """
    Download a Google Meet recording from Google Drive.

    Args:
        file_id:    Google Drive file ID.
        filename:   Desired filename for the saved file.
        upload_dir: Directory to save the file.

    Returns:
        Absolute path to the downloaded file.
    """
    token = _get_google_access_token()

    logger.info(f"Downloading Google Meet recording: {filename}")
    response = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"alt": "media"},
        stream=True,
        timeout=300,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Google Drive download failed: {response.status_code}")

    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    logger.info(f"Google Meet recording downloaded: {file_path} ({size_mb:.1f} MB)")
    return file_path
