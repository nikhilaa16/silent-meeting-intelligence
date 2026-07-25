"""
Microsoft Teams Integration
=============================

Uses Microsoft Graph API to fetch Teams meeting recordings.
Teams stores recordings in OneDrive / SharePoint.

Setup (one-time, 15 minutes):
  1. Go to https://portal.azure.com → Azure Active Directory → App Registrations
  2. Create a new app registration → Note down:
       - Application (client) ID
       - Directory (tenant) ID
  3. Create a Client Secret → Copy the value
  4. Add API Permissions:
       - Microsoft Graph → Application → CallRecords.Read.All
       - Microsoft Graph → Application → Files.Read.All
       - Microsoft Graph → Application → OnlineMeetings.Read.All
  5. Grant admin consent for the permissions
  6. Add to .env:
       TEAMS_TENANT_ID=your_tenant_id
       TEAMS_CLIENT_ID=your_app_client_id
       TEAMS_CLIENT_SECRET=your_client_secret

API Flow:
  POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
      ↓
  GET  /v1.0/communications/callRecords        (list recordings)
      ↓
  GET  OneDrive download URL                    (download recording)
      ↓
  POST /meetings/upload                         (SMI pipeline)

Note on Teams Recordings:
  Teams recordings are stored in the meeting organizer's OneDrive
  under "Recordings" folder. The Graph API provides access via
  CallRecords or by searching OneDrive for meeting recording files.
"""
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from ..config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Microsoft Identity Token Manager
# ─────────────────────────────────────────────

_teams_token_cache: dict = {"token": None, "expires_at": 0}


def _get_teams_access_token() -> str:
    """
    Get a Microsoft Graph API access token using Client Credentials flow.
    Tokens expire in 1 hour — cached and auto-refreshed.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If Teams credentials are not configured.
    """
    if not all([settings.TEAMS_TENANT_ID, settings.TEAMS_CLIENT_ID, settings.TEAMS_CLIENT_SECRET]):
        raise RuntimeError(
            "Microsoft Teams credentials not configured. Set TEAMS_TENANT_ID, "
            "TEAMS_CLIENT_ID, and TEAMS_CLIENT_SECRET in your .env file."
        )

    # Return cached token if still valid (with 60s buffer)
    if _teams_token_cache["token"] and time.time() < _teams_token_cache["expires_at"] - 60:
        return _teams_token_cache["token"]

    # Request a new token from Microsoft Identity Platform
    response = requests.post(
        f"https://login.microsoftonline.com/{settings.TEAMS_TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.TEAMS_CLIENT_ID,
            "client_secret": settings.TEAMS_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Microsoft Teams OAuth failed: {response.status_code} — {response.text[:200]}"
        )

    data = response.json()
    _teams_token_cache["token"] = data["access_token"]
    _teams_token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

    logger.info("Microsoft Teams access token refreshed successfully")
    return _teams_token_cache["token"]


# ─────────────────────────────────────────────
# Teams Meeting Recording Fetcher
# ─────────────────────────────────────────────

def list_teams_recordings(days_back: int = 30, max_results: int = 20) -> list[dict]:
    """
    Fetch Teams meeting recordings from OneDrive via Microsoft Graph API.

    Teams recordings are MP4 files stored in each user's OneDrive
    under the "Recordings" folder.

    Args:
        days_back:   How many days back to search.
        max_results: Maximum number of recordings to return.

    Returns:
        List of recording dicts with keys:
          - id, name, topic, start_time, size_mb, download_url, platform
    """
    token = _get_teams_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Search OneDrive for Teams recordings
    # Teams recordings are typically in /me/drive/root:/Recordings:
    search_query = f"createdDateTime ge {cutoff_date} and file ne null"

    # Try to find recordings in the Recordings folder
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/drive/root:/Recordings:/children",
        headers=headers,
        params={
            "$filter": f"createdDateTime ge '{cutoff_date}'",
            "$top": max_results,
            "$orderby": "createdDateTime desc",
            "$select": "id,name,createdDateTime,size,@microsoft.graph.downloadUrl,file",
        },
        timeout=15,
    )

    if response.status_code == 404:
        # Recordings folder doesn't exist or is named differently
        # Fall back to searching across all drives
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me/drive/root/search(q='Teams Recording')",
            headers=headers,
            params={
                "$top": max_results,
                "$select": "id,name,createdDateTime,size,@microsoft.graph.downloadUrl,file",
            },
            timeout=15,
        )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Microsoft Graph API error: {response.status_code} — {response.text[:300]}"
        )

    items = response.json().get("value", [])

    recordings = []
    for item in items:
        # Only include MP4 video files
        file_info = item.get("file", {})
        mime = file_info.get("mimeType", "")
        if "video" not in mime and not item.get("name", "").lower().endswith(".mp4"):
            continue

        size_bytes = item.get("size", 0)
        recordings.append({
            "id": item["id"],
            "name": item.get("name", "Teams Recording"),
            "topic": item.get("name", "Teams Recording").replace(".mp4", ""),
            "start_time": item.get("createdDateTime"),
            "file_size_mb": round(size_bytes / (1024 * 1024), 1),
            "download_url": item.get("@microsoft.graph.downloadUrl"),
            "file_type": "MP4",
            "platform": "teams",
        })

    logger.info(f"Found {len(recordings)} Teams recordings (last {days_back} days)")
    return recordings


def download_teams_recording(download_url: str, filename: str, upload_dir: str) -> str:
    """
    Download a Teams recording from OneDrive.

    Microsoft Graph pre-authenticated download URLs don't need an auth header —
    the token is embedded in the URL for a short time window.

    Args:
        download_url: Pre-authenticated download URL from Graph API.
        filename:     Desired filename for the saved file.
        upload_dir:   Directory to save the file.

    Returns:
        Absolute path to the downloaded file.
    """
    logger.info(f"Downloading Teams recording: {filename}")

    # Graph API pre-auth download URLs work without headers
    response = requests.get(download_url, stream=True, timeout=300)

    if response.status_code != 200:
        raise RuntimeError(f"Teams recording download failed: {response.status_code}")

    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    logger.info(f"Teams recording downloaded: {file_path} ({size_mb:.1f} MB)")
    return file_path
