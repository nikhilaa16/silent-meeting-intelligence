"""
FastAPI Backend — Silent Meeting Intelligence
=============================================

Endpoints:
  POST /meetings/upload     → Upload audio file, starts background processing
  GET  /meetings/{id}       → Poll for results (status + structured output)
  GET  /meetings            → List all processed meetings
  GET  /health              → Health check (public — no auth required)

Security:
  All endpoints except /health require an X-API-Key header.
  The key is set in .env → API_KEY. The dashboard sends it automatically.

Design decisions:
- Background tasks for processing: Whisper + LangGraph are IO bound — running
  them in BackgroundTasks keeps the upload endpoint fast (returns immediately).
- SQLite: Zero config, single file, perfect for single-machine deployment.
  Trade-off: Won't scale horizontally. For multi-server, swap the one-liner
  in database.py to postgresql+psycopg2://... — SQLAlchemy handles the rest.
- API Key auth over JWT: JWT is overkill for a single-tenant tool. A shared
  secret key is simpler, just as secure for this use case, and easier to rotate.
"""
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db, init_db
from .intelligence import analyze_meeting, detect_conflicts, semantic_search_meetings, chat_with_meeting_helper
from .models import MeetingDB, MeetingListItem, MeetingResult, MeetingUploadResponse, ChatRequest
from .whisper_service import transcribe_audio
from .auth import (
    UserRegisterRequest, UserLoginRequest, UserResponse, TokenResponse,
    register_user, login_user, get_current_user, require_admin, UserDB
)
from .integrations.zoom import list_zoom_recordings, download_zoom_recording
from .integrations.google_meet import list_google_meet_recordings, download_google_meet_recording
from .integrations.teams import list_teams_recordings, download_teams_recording

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Silent Meeting Intelligence",
    description="Transform meeting recordings into structured, actionable intelligence.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize database and upload directory on startup."""
    init_db()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Database initialized")
    logger.info(f"Upload directory: {settings.UPLOAD_DIR.absolute()}")
    logger.info("Silent Meeting Intelligence is running!")


# ─────────────────────────────────────────────
# Auth Endpoints (JWT)
# ─────────────────────────────────────────────

@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.
    Roles: "admin" (full access) or "viewer" (read-only).
    """
    return register_user(request, db)


@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login with email + password. Returns a JWT access token.
    Use the token as: Authorization: Bearer <token>
    """
    return login_user(request, db)


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: UserDB = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user


# ─────────────────────────────────────────────
# Platform Integrations (Zoom / Google Meet / Teams)
# ─────────────────────────────────────────────

@app.get("/integrations/status")
def integrations_status(_: str = Depends(verify_api_key)):
    """
    Check which platform integrations are configured.
    Returns enabled/disabled status for Zoom, Google Meet, and Teams.
    This endpoint is used by the dashboard to show the Integrations page.
    """
    return {
        "zoom": {
            "enabled": bool(settings.ZOOM_ACCOUNT_ID and settings.ZOOM_CLIENT_ID),
            "label": "Zoom",
            "description": "Fetch cloud recordings from Zoom meetings",
            "setup_url": "https://marketplace.zoom.us/develop/create",
            "required_env": ["ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"],
        },
        "google_meet": {
            "enabled": bool(settings.GOOGLE_SERVICE_ACCOUNT_INFO),
            "label": "Google Meet",
            "description": "Fetch Meet recordings saved to Google Drive",
            "setup_url": "https://console.cloud.google.com",
            "required_env": ["GOOGLE_SERVICE_ACCOUNT_INFO"],
        },
        "teams": {
            "enabled": bool(settings.TEAMS_TENANT_ID and settings.TEAMS_CLIENT_ID),
            "label": "Microsoft Teams",
            "description": "Fetch Teams meeting recordings from OneDrive",
            "setup_url": "https://portal.azure.com",
            "required_env": ["TEAMS_TENANT_ID", "TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET"],
        },
    }


@app.get("/integrations/zoom/recordings")
def get_zoom_recordings(
    days_back: int = 30,
    _: str = Depends(verify_api_key),
):
    """
    List Zoom cloud recordings from the last N days.
    Requires ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET in .env.
    """
    try:
        return list_zoom_recordings(days_back=days_back)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/integrations/zoom/process/{recording_id}", response_model=MeetingUploadResponse, status_code=202)
def process_zoom_recording(
    recording_id: str,
    download_url: str,
    topic: str = "Zoom Meeting",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Download a Zoom recording and push it through the SMI intelligence pipeline.
    Returns a meeting_id immediately. Poll GET /meetings/{meeting_id} for results.
    """
    import uuid
    meeting_id = str(uuid.uuid4())
    filename = f"{meeting_id}_zoom.mp4"
    saved_path = str(settings.UPLOAD_DIR / filename)

    # Create DB record immediately
    meeting = MeetingDB(id=meeting_id, filename=f"[Zoom] {topic}")
    db.add(meeting)
    db.commit()

    # Download + process in background
    def _download_and_process():
        try:
            file_path = download_zoom_recording(download_url, filename, str(settings.UPLOAD_DIR))
            _process_meeting_background(meeting_id, file_path)
        except Exception as e:
            logger.error(f"Zoom recording processing failed: {e}")

    background_tasks.add_task(_download_and_process)

    return MeetingUploadResponse(
        meeting_id=meeting_id,
        status="processing",
        message=f"Zoom recording '{topic}' queued. Poll /meetings/{meeting_id} for results.",
    )


@app.get("/integrations/google-meet/recordings")
def get_google_meet_recordings(
    days_back: int = 30,
    _: str = Depends(verify_api_key),
):
    """
    List Google Meet recordings from Google Drive (last N days).
    Requires GOOGLE_SERVICE_ACCOUNT_INFO in .env.
    """
    try:
        return list_google_meet_recordings(days_back=days_back)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/integrations/google-meet/process/{file_id}", response_model=MeetingUploadResponse, status_code=202)
def process_google_meet_recording(
    file_id: str,
    topic: str = "Google Meet",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Download a Google Meet recording from Drive and process it through SMI.
    """
    import uuid
    meeting_id = str(uuid.uuid4())
    filename = f"{meeting_id}_gmeet.mp4"

    meeting = MeetingDB(id=meeting_id, filename=f"[Google Meet] {topic}")
    db.add(meeting)
    db.commit()

    def _download_and_process():
        try:
            file_path = download_google_meet_recording(file_id, filename, str(settings.UPLOAD_DIR))
            _process_meeting_background(meeting_id, file_path)
        except Exception as e:
            logger.error(f"Google Meet recording processing failed: {e}")

    background_tasks.add_task(_download_and_process)

    return MeetingUploadResponse(
        meeting_id=meeting_id,
        status="processing",
        message=f"Google Meet recording '{topic}' queued. Poll /meetings/{meeting_id} for results.",
    )


@app.get("/integrations/teams/recordings")
def get_teams_recordings(
    days_back: int = 30,
    _: str = Depends(verify_api_key),
):
    """
    List Microsoft Teams meeting recordings (last N days).
    Requires TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET in .env.
    """
    try:
        return list_teams_recordings(days_back=days_back)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/integrations/teams/process/{recording_id}", response_model=MeetingUploadResponse, status_code=202)
def process_teams_recording(
    recording_id: str,
    download_url: str,
    topic: str = "Teams Meeting",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Download a Teams recording from OneDrive and process it through SMI.
    """
    import uuid
    meeting_id = str(uuid.uuid4())
    filename = f"{meeting_id}_teams.mp4"

    meeting = MeetingDB(id=meeting_id, filename=f"[Teams] {topic}")
    db.add(meeting)
    db.commit()

    def _download_and_process():
        try:
            file_path = download_teams_recording(download_url, filename, str(settings.UPLOAD_DIR))
            _process_meeting_background(meeting_id, file_path)
        except Exception as e:
            logger.error(f"Teams recording processing failed: {e}")

    background_tasks.add_task(_download_and_process)

    return MeetingUploadResponse(
        meeting_id=meeting_id,
        status="processing",
        message=f"Teams recording '{topic}' queued. Poll /meetings/{meeting_id} for results.",
    )


# ─────────────────────────────────────────────
# Authentication Dependency
# ─────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")) -> str:
    """
    FastAPI dependency — validates the X-API-Key header on every protected request.

    Why header-based API key over JWT?
    - JWT is stateful and requires a token store or short expiry — complex for
      a single-tenant tool where one user controls everything.
    - A shared API key is simpler, equally secure, and trivially rotatable
      (just change API_KEY in .env and restart).

    Usage:
        Set X-API-Key: your-key in every request header.
        The Streamlit dashboard reads the key from .env and sends it automatically.
    """
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Set X-API-Key header with your API_KEY from .env",
        )
    return x_api_key


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Public health check — no auth required. Used by dashboard to verify backend is up."""
    return {
        "status": "healthy",
        "service": "Silent Meeting Intelligence",
        "version": "1.0.0",
    }


@app.get("/debug")
def debug_check():
    return {
        "model": settings.GROQ_LLM_MODEL,
        "key_prefix": settings.GROQ_API_KEY[:10] if settings.GROQ_API_KEY else "None",
        "key_length": len(settings.GROQ_API_KEY) if settings.GROQ_API_KEY else 0,
        "upload_dir": str(settings.UPLOAD_DIR),
        "db_path": settings.DB_PATH,
    }


@app.post("/meetings/upload", response_model=MeetingUploadResponse, status_code=202)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio or video file of the meeting"),
    language: str = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Upload a meeting recording. Processing starts immediately in the background.

    Multi-Language Support:
      Pass ?language=hi for Hindi, ?language=ta for Tamil, ?language=fr for French.
      Leave blank for automatic language detection (recommended).
      Supported ISO 639-1 codes: en, hi, ta, te, kn, ml, fr, de, es, ja, zh, ar, pt, ru

    Supported formats: MP3, MP4, WAV, M4A, OGG, WEBM
    Returns meeting_id immediately. Poll GET /meetings/{meeting_id} for results.
    """
    # ── Validate file format ────────────────────────────────────────────
    ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".webm", ".mpeg"}
    file_ext = Path(file.filename or "").suffix.lower()

    if not file_ext:
        raise HTTPException(status_code=400, detail="File has no extension. Cannot determine format.")

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{file_ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # ── Validate file size ──────────────────────────────────────────────
    # Read into memory to check size, then write to disk
    # Trade-off: loads file into RAM. For very large files (>500MB), stream to disk first.
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)

    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: {settings.MAX_FILE_SIZE_MB} MB.",
        )

    if size_mb == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # ── Save file to disk ───────────────────────────────────────────────
    meeting_id = str(uuid.uuid4())
    saved_path = settings.UPLOAD_DIR / f"{meeting_id}{file_ext}"

    try:
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file to disk: {e}")

    logger.info(f"[{meeting_id}] Saved: {file.filename} ({size_mb:.1f} MB)")

    # ── Create database record ──────────────────────────────────────────
    meeting = MeetingDB(id=meeting_id, filename=file.filename or "unknown")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # ── Kick off background processing ─────────────────────────────────
    background_tasks.add_task(_process_meeting_background, meeting_id, str(saved_path), language)

    return MeetingUploadResponse(
        meeting_id=meeting_id,
        status="processing",
        message=f"Meeting '{file.filename}' uploaded. Processing started. Poll /meetings/{meeting_id} for results.",
    )


@app.get("/meetings/search")
def search_meetings(
    query: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Search past completed meetings using a lexical RAG pipeline (TF-IDF keyword matching + LLM synthesis).

    Query example: "What did we decide about the database?"
    """
    completed_meetings = (
        db.query(MeetingDB)
        .filter(
            MeetingDB.status == "completed",
            MeetingDB.transcript.isnot(None),
        )
        .all()
    )

    meetings_data = []
    for m in completed_meetings:
        meetings_data.append({
            "id": m.id,
            "filename": m.filename,
            "transcript": m.transcript,
            "created_at": m.created_at
        })

    return semantic_search_meetings(query, meetings_data)


@app.get("/meetings/tasks")
def list_all_tasks(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Aggregate and list all action items across all completed meetings."""
    completed = db.query(MeetingDB).filter(MeetingDB.status == "completed").all()
    all_tasks = []
    for m in completed:
        if m.action_items:
            for idx, item in enumerate(m.action_items):
                task_dict = dict(item)
                task_dict["meeting_id"] = m.id
                task_dict["meeting_filename"] = m.filename
                task_dict["task_index"] = idx
                all_tasks.append(task_dict)
    return all_tasks


@app.get("/meetings/{meeting_id}", response_model=MeetingResult)
def get_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Get the full result for a specific meeting.

    Status values:
    - "processing" → pipeline still running, check back in a few seconds
    - "completed"  → all intelligence extracted and available
    - "failed"     → error occurred, check error_message field
    """
    meeting = db.query(MeetingDB).filter(MeetingDB.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found.")
    return meeting


@app.post("/meetings/{meeting_id}/chat")
def chat_with_meeting(
    meeting_id: str,
    request_data: ChatRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Chat with a specific meeting transcript.
    """
    meeting = db.query(MeetingDB).filter(MeetingDB.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found.")

    if not meeting.transcript:
        raise HTTPException(
            status_code=400,
            detail="This meeting has no transcript yet. Wait for processing to complete.",
        )

    response_text = chat_with_meeting_helper(
        meeting.transcript,
        request_data.message,
        request_data.history,
    )
    return {"response": response_text}


@app.get("/meetings", response_model=list[MeetingListItem])
def list_meetings(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all meetings ordered by creation date, newest first."""
    return db.query(MeetingDB).order_by(MeetingDB.created_at.desc()).all()


@app.post("/meetings/{meeting_id}/tasks/{task_idx}/toggle")
def toggle_meeting_task(
    meeting_id: str,
    task_idx: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Toggle the completed status of an action item at a specific index."""
    meeting = db.query(MeetingDB).filter(MeetingDB.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    action_items = list(meeting.action_items) if meeting.action_items else []
    if task_idx < 0 or task_idx >= len(action_items):
        raise HTTPException(status_code=404, detail="Task index out of range.")

    # Mutate a copy to ensure SQLAlchemy registers the change
    item = dict(action_items[task_idx])
    item["completed"] = not item.get("completed", False)
    action_items[task_idx] = item

    meeting.action_items = action_items
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return {"status": "success", "action_items": meeting.action_items}


@app.post("/meetings/{meeting_id}/conflicts/{conflict_idx}/resolve")
def resolve_meeting_conflict(
    meeting_id: str,
    conflict_idx: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Dismiss/resolve a cross-meeting conflict by index."""
    meeting = db.query(MeetingDB).filter(MeetingDB.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    conflicts = list(meeting.conflicts) if meeting.conflicts else []
    if conflict_idx < 0 or conflict_idx >= len(conflicts):
        raise HTTPException(status_code=404, detail="Conflict index out of range.")

    conflicts.pop(conflict_idx)
    meeting.conflicts = conflicts
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return {"status": "success", "conflicts": meeting.conflicts}


@app.delete("/meetings/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Permanently delete a meeting and its data from the database."""
    meeting = db.query(MeetingDB).filter(MeetingDB.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    db.delete(meeting)
    db.commit()


# ─────────────────────────────────────────────
# Background Processing Task
# ─────────────────────────────────────────────

def _process_meeting_background(meeting_id: str, file_path: str, language: str = None) -> None:
    """
    Full processing pipeline — runs after the upload response is sent.

    Args:
        meeting_id: Unique UUID for this meeting.
        file_path:  Absolute path to the uploaded audio file.
        language:   Optional ISO 639-1 language code for transcription.
                    Pass None or "auto" for automatic language detection.

    Steps:
    1. Transcribe audio with Groq Whisper API (with optional language param)
    2. Validate transcript is not empty
    3. Run LangGraph 5-agent intelligence pipeline
    4. Run cross-meeting conflict detection against past decisions
    5. Persist all results to SQLite / PostgreSQL
    """
    db = next(get_db())

    def _update_db(status: str, **kwargs):
        """Helper to update meeting record — encapsulates the ORM update pattern."""
        try:
            meeting = db.query(MeetingDB).filter(MeetingDB.id == meeting_id).first()
            if meeting:
                meeting.status = status
                for key, value in kwargs.items():
                    setattr(meeting, key, value)
                db.commit()
        except Exception as db_err:
            logger.error(f"[{meeting_id}] DB update failed: {db_err}")

    try:
        # ── Step 1: Transcription ───────────────────────────────────────
        logger.info(f"[{meeting_id}] Starting transcription | language: {language or 'auto'}...")
        transcript = transcribe_audio(file_path, language=language)

        # ── Step 2: Validate transcript ─────────────────────────────────
        if not transcript or len(transcript.strip()) < 10:
            raise ValueError(
                "Transcript is empty or too short. "
                "The audio may be silent, too quiet, or in an unsupported language."
            )

        logger.info(f"[{meeting_id}] Transcription done — {len(transcript.split())} words")

        # ── Step 3: Intelligence pipeline ───────────────────────────────
        logger.info(f"[{meeting_id}] Running 4-agent intelligence pipeline...")
        result = analyze_meeting(transcript)
        logger.info(f"[{meeting_id}] Pipeline done — "
                    f"{len(result.get('decisions', []))} decisions, "
                    f"{len(result.get('action_items', []))} action items, "
                    f"{len(result.get('open_questions', []))} open questions")

        # ── Step 4: Cross-meeting conflict detection ─────────────────────
        conflicts = []
        new_decisions = result.get("decisions", [])

        if new_decisions:
            logger.info(f"[{meeting_id}] Running conflict detection...")

            # Fetch all decisions from PAST meetings (not the current one)
            past_meetings = (
                db.query(MeetingDB)
                .filter(
                    MeetingDB.id != meeting_id,
                    MeetingDB.status == "completed",
                    MeetingDB.decisions.isnot(None),
                )
                .all()
            )

            # Flatten past decisions into a list with meeting context
            past_decisions = []
            for m in past_meetings:
                if m.decisions:
                    for decision in m.decisions:
                        past_decisions.append({
                            "decision": decision,
                            "meeting_id": m.id,
                            "filename": m.filename,
                            "created_at": str(m.created_at)[:10] if m.created_at else "Unknown",
                        })

            if past_decisions:
                conflicts = detect_conflicts(new_decisions, past_decisions)
                logger.info(f"[{meeting_id}] Conflict detection done — {len(conflicts)} conflicts found")
            else:
                logger.info(f"[{meeting_id}] No past meetings to compare against — skipping conflict detection")

        # ── Step 5: Save to database ─────────────────────────────────────
        _update_db(
            "completed",
            transcript=transcript,
            decisions=result.get("decisions", []),
            action_items=result.get("action_items", []),
            open_questions=result.get("open_questions", []),
            summary=result.get("summary", ""),
            conflicts=conflicts,
            email_draft=result.get("email_draft", ""),
            completed_at=datetime.utcnow(),
        )

        logger.info(f"[{meeting_id}] Processing complete!")

    except ValueError as ve:
        # Validation errors — user-facing, not a system crash
        logger.warning(f"[{meeting_id}] Validation error: {ve}")
        _update_db("failed", error_message=str(ve), completed_at=datetime.utcnow())

    except Exception as e:
        # Unexpected errors — log full traceback for debugging
        logger.error(f"[{meeting_id}] Unexpected error: {e}", exc_info=True)
        _update_db("failed", error_message=f"Processing error: {str(e)}", completed_at=datetime.utcnow())

    finally:
        db.close()
