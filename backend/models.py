"""
Data models:
- SQLAlchemy ORM models  → define database tables
- Pydantic schemas       → define API request/response shapes
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, JSON, String, Text

from .database import Base


# ─────────────────────────────────────────────
# SQLAlchemy ORM Model (database table)
# ─────────────────────────────────────────────

class MeetingDB(Base):
    """One row per meeting processed."""
    __tablename__ = "meetings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    status = Column(String, default="processing")  # processing | completed | failed

    # Raw transcript from Whisper
    transcript = Column(Text, nullable=True)

    # Extracted intelligence (stored as JSON arrays/objects)
    decisions = Column(JSON, nullable=True)       # list[str]
    action_items = Column(JSON, nullable=True)    # list[dict]
    open_questions = Column(JSON, nullable=True)  # list[str]
    summary = Column(Text, nullable=True)
    conflicts = Column(JSON, nullable=True)       # list[dict] — cross-meeting conflicts
    email_draft = Column(Text, nullable=True)     # Follow-up email draft

    # Error message if processing failed
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ─────────────────────────────────────────────
# Pydantic Schemas (API contracts)
# ─────────────────────────────────────────────

class ActionItem(BaseModel):
    """A single task extracted from the meeting."""
    task: str
    owner: str = "Unassigned"
    deadline: Optional[str] = None
    priority: str = "medium"  # high | medium | low


class MeetingUploadResponse(BaseModel):
    """Returned immediately after a file is uploaded."""
    meeting_id: str
    status: str
    message: str


class MeetingResult(BaseModel):
    """Full meeting result returned once processing is complete."""
    id: str
    filename: str
    status: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    decisions: Optional[list[str]] = None
    action_items: Optional[list[dict]] = None
    open_questions: Optional[list[str]] = None
    conflicts: Optional[list[dict]] = None
    email_draft: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MeetingListItem(BaseModel):
    """Lightweight item for the meetings list view."""
    id: str
    filename: str
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
