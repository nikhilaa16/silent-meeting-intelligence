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
from .intelligence import analyze_meeting, detect_conflicts, semantic_search_meetings
from .models import MeetingDB, MeetingListItem, MeetingResult, MeetingUploadResponse
from .whisper_service import transcribe_audio

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


@app.post("/meetings/upload", response_model=MeetingUploadResponse, status_code=202)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio or video file of the meeting"),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Upload a meeting recording. Processing starts immediately in the background.

    Supported formats: MP3, MP4, WAV, M4A, OGG, WEBM
    Returns meeting_id immediately. Poll GET /meetings/{meeting_id} for results.

    Error cases handled:
    - Unsupported file format → 400
    - File exceeds size limit → 400
    - Disk write failure     → 500
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
    background_tasks.add_task(_process_meeting_background, meeting_id, str(saved_path))

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
    Search past completed meetings using a semantic RAG pipeline.

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


@app.get("/meetings", response_model=list[MeetingListItem])
def list_meetings(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all meetings ordered by creation date, newest first."""
    return db.query(MeetingDB).order_by(MeetingDB.created_at.desc()).all()


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

def _process_meeting_background(meeting_id: str, file_path: str) -> None:
    """
    Full processing pipeline — runs after the upload response is sent.

    Steps:
    1. Transcribe audio with Groq Whisper API
    2. Validate transcript is not empty
    3. Run LangGraph 4-agent intelligence pipeline
    4. Run cross-meeting conflict detection against past decisions
    5. Persist all results to SQLite

    Error handling:
    - Empty transcript (silent audio) → fails with clear message
    - Groq API error                  → fails with API error message
    - LangGraph failure               → fails gracefully, saves partial results
    - DB write failure                → logs error, best effort save
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
        logger.info(f"[{meeting_id}] Starting transcription...")
        transcript = transcribe_audio(file_path)

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
