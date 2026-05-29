"""
Test Suite — Silent Meeting Intelligence
========================================

Tests for the core intelligence pipeline.
Run with: pytest tests/ -v

Why these tests?
- _safe_json_parse is called on every LLM response — critical to get right
- analyze_meeting is the heart of the system — must not crash on edge inputs
- detect_conflicts must return a list always — dashboard depends on this

We mock the LLM calls using unittest.mock so tests run:
  - Without a real Groq API key
  - Without internet access
  - In under 1 second (no actual API calls)
"""
import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
# Tests: _safe_json_parse
# ─────────────────────────────────────────────

class TestSafeJsonParse:
    """Tests for the JSON parsing utility used on every LLM response."""

    def test_parses_clean_json_dict(self):
        """Standard case — LLM returns clean JSON object."""
        from backend.intelligence import _safe_json_parse
        result = _safe_json_parse('{"decisions": ["We chose PostgreSQL", "Budget approved"]}', "decisions")
        assert result == ["We chose PostgreSQL", "Budget approved"]

    def test_parses_json_array_directly(self):
        """Some LLMs return a bare array instead of a wrapped object."""
        from backend.intelligence import _safe_json_parse
        result = _safe_json_parse('["Decision one", "Decision two"]', "decisions")
        assert result == ["Decision one", "Decision two"]

    def test_strips_markdown_code_fences(self):
        """LLMs often wrap JSON in ```json ... ``` — we must handle this."""
        from backend.intelligence import _safe_json_parse
        text = '```json\n{"decisions": ["We approved the budget"]}\n```'
        result = _safe_json_parse(text, "decisions")
        assert result == ["We approved the budget"]

    def test_returns_empty_list_on_invalid_json(self):
        """If LLM returns garbage, we must not crash — return empty list."""
        from backend.intelligence import _safe_json_parse
        result = _safe_json_parse("Sorry, I couldn't analyze the meeting.", "decisions")
        assert result == []

    def test_returns_empty_list_on_missing_key(self):
        """If the key doesn't exist in the JSON, return empty list."""
        from backend.intelligence import _safe_json_parse
        result = _safe_json_parse('{"wrong_key": ["something"]}', "decisions")
        assert result == []

    def test_returns_empty_list_on_empty_string(self):
        """Empty string input must not crash."""
        from backend.intelligence import _safe_json_parse
        result = _safe_json_parse("", "decisions")
        assert result == []


# ─────────────────────────────────────────────
# Tests: analyze_meeting (with mocked LLM)
# ─────────────────────────────────────────────

SAMPLE_TRANSCRIPT = """
Good morning team. Let's start the standup.
We have decided to use FastAPI for the backend.
John will set up the repository by Friday.
We still need to decide on the database — PostgreSQL or MongoDB.
"""

class TestAnalyzeMeeting:
    """Tests for the full 4-agent LangGraph pipeline."""

    @patch("backend.intelligence._get_llm")
    def test_returns_all_required_keys(self, mock_get_llm):
        """Pipeline must always return decisions, action_items, open_questions, summary."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"decisions": [], "action_items": [], "open_questions": []}'
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import analyze_meeting
        result = analyze_meeting(SAMPLE_TRANSCRIPT)

        assert "decisions" in result
        assert "action_items" in result
        assert "open_questions" in result
        assert "summary" in result

    @patch("backend.intelligence._get_llm")
    def test_decisions_is_always_a_list(self, mock_get_llm):
        """decisions must always be a list, never None."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"decisions": ["We chose FastAPI"]}'
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import analyze_meeting
        result = analyze_meeting(SAMPLE_TRANSCRIPT)

        assert isinstance(result["decisions"], list)

    @patch("backend.intelligence._get_llm")
    def test_action_items_is_always_a_list(self, mock_get_llm):
        """action_items must always be a list, never None."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = json.dumps({
            "action_items": [{"task": "Set up repo", "owner": "John", "deadline": "Friday", "priority": "high"}]
        })
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import analyze_meeting
        result = analyze_meeting(SAMPLE_TRANSCRIPT)

        assert isinstance(result["action_items"], list)

    @patch("backend.intelligence._get_llm")
    def test_does_not_crash_on_empty_transcript(self, mock_get_llm):
        """Pipeline must handle empty/short transcripts without crashing."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"decisions": []}'
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import analyze_meeting
        result = analyze_meeting("")

        assert result is not None
        assert "decisions" in result

    @patch("backend.intelligence._get_llm")
    def test_handles_llm_returning_invalid_json(self, mock_get_llm):
        """If LLM returns non-JSON, pipeline must not crash — return empty lists."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "I am sorry, I cannot analyze this meeting."
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import analyze_meeting
        result = analyze_meeting(SAMPLE_TRANSCRIPT)

        assert isinstance(result["decisions"], list)
        assert isinstance(result["action_items"], list)
        assert isinstance(result["open_questions"], list)


# ─────────────────────────────────────────────
# Tests: detect_conflicts
# ─────────────────────────────────────────────

class TestDetectConflicts:
    """Tests for cross-meeting conflict detection."""

    def test_returns_empty_list_when_no_past_decisions(self):
        """No past decisions means no conflicts possible."""
        from backend.intelligence import detect_conflicts
        result = detect_conflicts(["We chose PostgreSQL"], [])
        assert result == []

    def test_returns_empty_list_when_no_new_decisions(self):
        """No new decisions means nothing to conflict with."""
        from backend.intelligence import detect_conflicts
        result = detect_conflicts([], [{"decision": "We chose MongoDB", "filename": "meeting1.mp3", "created_at": "2025-01-01"}])
        assert result == []

    @patch("backend.intelligence._get_llm")
    def test_returns_list_always(self, mock_get_llm):
        """detect_conflicts must always return a list, never crash."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"conflicts": []}'
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import detect_conflicts
        result = detect_conflicts(
            ["We chose PostgreSQL"],
            [{"decision": "We chose MongoDB", "filename": "old.mp3", "created_at": "2025-01-01"}]
        )
        assert isinstance(result, list)

    @patch("backend.intelligence._get_llm")
    def test_handles_llm_failure_gracefully(self, mock_get_llm):
        """If LLM crashes, detect_conflicts must return [] not raise an exception."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Groq API rate limit exceeded")
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import detect_conflicts
        result = detect_conflicts(
            ["We chose PostgreSQL"],
            [{"decision": "We chose MongoDB", "filename": "old.mp3", "created_at": "2025-01-01"}]
        )
        assert result == []


# ─────────────────────────────────────────────
# Tests: FastAPI Endpoints
# ─────────────────────────────────────────────

class TestAPI:
    """Integration tests for FastAPI endpoints using TestClient."""

    def setup_method(self):
        """Set up test client before each test."""
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.database import init_db
        init_db()  # Re-create database and tables with new schema if missing
        self.client = TestClient(app)
        self.headers = {"X-API-Key": "silent-meeting-super-secret-2025"}

    def test_health_check_no_auth_required(self):
        """/health must be publicly accessible — no API key required."""
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_list_meetings_requires_auth(self):
        """Protected endpoints must reject requests without API key."""
        response = self.client.get("/meetings")
        assert response.status_code == 422  # Missing required header

    def test_list_meetings_rejects_wrong_key(self):
        """Wrong API key must return 401."""
        response = self.client.get("/meetings", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

    def test_list_meetings_with_valid_key(self):
        """Valid API key must return 200 with a list."""
        response = self.client.get("/meetings", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_upload_rejects_unsupported_format(self):
        """Uploading a .txt file must return 400."""
        response = self.client.post(
            "/meetings/upload",
            files={"file": ("meeting.txt", b"hello world", "text/plain")},
            headers=self.headers,
        )
        assert response.status_code == 400

    def test_upload_rejects_empty_file(self):
        """Uploading an empty file must return 400."""
        response = self.client.post(
            "/meetings/upload",
            files={"file": ("meeting.mp3", b"", "audio/mpeg")},
            headers=self.headers,
        )
        assert response.status_code == 400

    def test_get_nonexistent_meeting_returns_404(self):
        """Fetching a meeting that doesn't exist must return 404."""
        response = self.client.get(
            "/meetings/nonexistent-meeting-id-12345",
            headers=self.headers,
        )
        assert response.status_code == 404

    def test_search_endpoint_requires_auth(self):
        """Search endpoint must return 422 if API key is missing."""
        response = self.client.get("/meetings/search?query=test")
        assert response.status_code == 422

    def test_search_endpoint_rejects_wrong_key(self):
        """Search endpoint must return 401 on incorrect API key."""
        response = self.client.get("/meetings/search?query=test", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401

    def test_search_endpoint_returns_json(self):
        """Search endpoint must return 200 and search response when authenticated."""
        response = self.client.get("/meetings/search?query=database", headers=self.headers)
        assert response.status_code == 200
        assert "answer" in response.json()

    def test_list_all_tasks_endpoint(self):
        """GET /meetings/tasks should aggregate all tasks in the system."""
        from backend.database import SessionLocal
        from backend.models import MeetingDB
        
        db = SessionLocal()
        meeting1 = MeetingDB(
            id="test-meeting-t1",
            filename="meeting1.mp3",
            status="completed",
            action_items=[{"task": "Task 1", "owner": "Alice", "priority": "high", "completed": False}]
        )
        meeting2 = MeetingDB(
            id="test-meeting-t2",
            filename="meeting2.mp3",
            status="completed",
            action_items=[{"task": "Task 2", "owner": "Bob", "priority": "low", "completed": True}]
        )
        db.add(meeting1)
        db.add(meeting2)
        db.commit()
        db.close()

        try:
            response = self.client.get("/meetings/tasks", headers=self.headers)
            assert response.status_code == 200
            tasks = response.json()
            assert len(tasks) >= 2
            
            # Find our tasks in the list
            t1 = next((t for t in tasks if t["meeting_id"] == "test-meeting-t1"), None)
            t2 = next((t for t in tasks if t["meeting_id"] == "test-meeting-t2"), None)
            
            assert t1 is not None
            assert t1["task"] == "Task 1"
            assert t1["owner"] == "Alice"
            assert t1["completed"] is False
            
            assert t2 is not None
            assert t2["task"] == "Task 2"
            assert t2["owner"] == "Bob"
            assert t2["completed"] is True
        finally:
            db = SessionLocal()
            db.query(MeetingDB).filter(MeetingDB.id.in_(["test-meeting-t1", "test-meeting-t2"])).delete()
            db.commit()
            db.close()

    def test_chat_endpoint_requires_auth(self):
        """Chat endpoint must return 422 if API key is missing."""
        response = self.client.post("/meetings/meeting-id/chat", json={"message": "hello"})
        assert response.status_code == 422

    def test_chat_endpoint_returns_404_if_not_found(self):
        """Chat endpoint must return 404 if meeting doesn't exist."""
        response = self.client.post(
            "/meetings/nonexistent-id/chat",
            json={"message": "hello", "history": []},
            headers=self.headers
        )
        assert response.status_code == 404

    def test_toggle_task_completes_and_toggles(self):
        """Toggling an action item should modify its 'completed' state in the database."""
        from backend.database import SessionLocal
        from backend.models import MeetingDB
        
        db = SessionLocal()
        meeting = MeetingDB(
            id="test-meeting-toggle",
            filename="test.mp3",
            status="completed",
            action_items=[{"task": "Build feature", "owner": "Nik", "priority": "high", "completed": False}]
        )
        db.add(meeting)
        db.commit()
        db.close()

        try:
            # First toggle: False -> True
            response = self.client.post(
                "/meetings/test-meeting-toggle/tasks/0/toggle",
                headers=self.headers
            )
            assert response.status_code == 200
            assert response.json()["action_items"][0]["completed"] is True

            # Second toggle: True -> False
            response = self.client.post(
                "/meetings/test-meeting-toggle/tasks/0/toggle",
                headers=self.headers
            )
            assert response.status_code == 200
            assert response.json()["action_items"][0]["completed"] is False
        finally:
            db = SessionLocal()
            db.query(MeetingDB).filter(MeetingDB.id == "test-meeting-toggle").delete()
            db.commit()
            db.close()

    def test_resolve_conflict_removes_from_list(self):
        """Resolving a conflict should remove it from the conflicts JSON array."""
        from backend.database import SessionLocal
        from backend.models import MeetingDB
        
        db = SessionLocal()
        meeting = MeetingDB(
            id="test-meeting-resolve",
            filename="test.mp3",
            status="completed",
            conflicts=[{"new_decision": "A", "past_decision": "B", "past_meeting": "old.mp3", "explanation": "x"}]
        )
        db.add(meeting)
        db.commit()
        db.close()

        try:
            response = self.client.post(
                "/meetings/test-meeting-resolve/conflicts/0/resolve",
                headers=self.headers
            )
            assert response.status_code == 200
            assert len(response.json()["conflicts"]) == 0
        finally:
            db = SessionLocal()
            db.query(MeetingDB).filter(MeetingDB.id == "test-meeting-resolve").delete()
            db.commit()
            db.close()


# ─────────────────────────────────────────────
# Tests: Semantic RAG Search & Email Agent
# ─────────────────────────────────────────────

class TestSemanticSearchAndEmailAgent:
    """Tests for RAG retrieval logic and the follow-up email agent."""

    def test_search_returns_empty_response_on_empty_db(self):
        """RAG search should state there are no meetings when DB is empty."""
        from backend.intelligence import semantic_search_meetings
        result = semantic_search_meetings("what about budget?", [])
        assert "no past meetings" in result["answer"].lower()
        assert result["sources"] == []

    def test_search_retrieves_matching_paragraph(self):
        """RAG search should score and select relevant snippets based on keywords."""
        from backend.intelligence import semantic_search_meetings
        meetings = [
            {
                "id": "1",
                "filename": "meeting1.mp3",
                "created_at": "2025-01-01",
                "transcript": "We decided to allocate fifty thousand dollars for marketing next quarter."
            },
            {
                "id": "2",
                "filename": "meeting2.mp3",
                "created_at": "2025-01-02",
                "transcript": "John is going to deploy the API server using Docker on Friday morning."
            }
        ]

        with patch("backend.intelligence._get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value.content = "Answer: Marketing budget is fifty thousand dollars."
            mock_get_llm.return_value = mock_llm

            result = semantic_search_meetings("marketing budget", meetings)

            assert "fifty thousand dollars" in result["answer"]
            assert len(result["sources"]) > 0
            assert result["sources"][0]["filename"] == "meeting1.mp3"

    @patch("backend.intelligence._get_llm")
    def test_pipeline_includes_email_draft(self, mock_get_llm):
        """The 5-agent pipeline must include an email_draft in its output."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = 'Subject: Follow-up email draft\nHi Team...'
        mock_get_llm.return_value = mock_llm

        from backend.intelligence import analyze_meeting
        result = analyze_meeting("Today we decided to migrate our DB to Postgres.")

        assert "email_draft" in result
        assert result["email_draft"] is not None
