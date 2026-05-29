# Silent Meeting Intelligence 🎙️

> Transform your meeting recordings into structured, actionable intelligence using a 4-agent AI pipeline.

---

## What It Does

Upload any meeting audio. Get back:

| Output | Description |
|---|---|
| ✅ **Decisions** | Everything that was finalized and agreed upon |
| 🎯 **Action Items** | Who is doing what, by when, with priority |
| ❓ **Open Questions** | What was left unresolved |
| 📋 **Summary** | Clean executive summary in 3–5 sentences |

---

## Architecture

```
Meeting Recording (MP3/MP4/WAV)
        │
        ▼
  [Groq Whisper API]          ← Transcription (whisper-large-v3-turbo)
        │
        ▼
  [LangGraph Pipeline]        ← 4-node state machine
  ├── Node 1: Extract Decisions
  ├── Node 2: Extract Action Items (owner + deadline + priority)
  ├── Node 3: Extract Open Questions
  └── Node 4: Generate Summary
        │
        ▼
  [FastAPI Backend]           ← REST API (async, background processing)
        │
        ▼
  [SQLite Database]           ← Meeting history + results
        │
        ▼
  [Streamlit Dashboard]       ← Real-time UI with tabs
```

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Transcription | Groq Whisper API | 10x faster than local, free tier, no GPU needed |
| AI Agents | LangGraph | Production-standard stateful agent orchestration |
| LLM | Llama 3.3 70B via Groq | Free, fast, accurate structured extraction |
| Backend | FastAPI | Async, auto-docs, industry standard |
| Database | SQLite + SQLAlchemy | Zero config, perfect for single-machine deployment |
| Frontend | Streamlit | Fast to build, easy to demo |

---

## Setup

### 1. Get a Free Groq API Key
Go to [console.groq.com](https://console.groq.com) → Sign up → Create API Key (free, no credit card)

### 2. Create Environment File
```bash
cp .env.example .env
# Edit .env and paste your GROQ_API_KEY
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Backend
```bash
python run_backend.py
```
Backend will be live at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 5. Run the Dashboard (new terminal)
```bash
streamlit run dashboard/app.py
```
Dashboard at: http://localhost:8501

---

## Usage

1. Open http://localhost:8501
2. Upload any meeting recording (MP3, MP4, WAV, M4A)
3. Click **Analyze Meeting**
4. Wait 30–90 seconds while the pipeline runs
5. View results in the tabbed interface

---

## Project Structure

```
silent-meeting-intelligence/
├── backend/
│   ├── config.py         → Settings from .env
│   ├── database.py       → SQLite setup
│   ├── models.py         → ORM + Pydantic schemas
│   ├── whisper_service.py → Groq Whisper transcription
│   ├── intelligence.py   → LangGraph 4-agent pipeline ⭐
│   └── main.py           → FastAPI endpoints
├── dashboard/
│   └── app.py            → Streamlit UI
├── run_backend.py        → Start backend
├── requirements.txt
├── .env.example
└── README.md
```

---

## Trade-off Decisions

**Why Groq instead of local Whisper?**
Running Whisper locally on CPU takes 2–5x real-time (5 min meeting = 10–25 min processing). Groq's API uses the same model and returns results in seconds. The free tier is more than sufficient for development and demo.

**Why SQLite instead of PostgreSQL?**
This project runs on a single machine. SQLite has zero setup overhead, stores everything in a single file, and handles hundreds of concurrent reads fine. For a multi-server production deployment, the swap to PostgreSQL is a one-line change in `database.py`.

**Why LangGraph instead of plain LangChain?**
LangGraph gives us an explicit state machine where each extraction agent is independently testable and the flow is auditable. Plain LangChain chains are harder to debug when one extraction step fails. LangGraph also makes it trivial to add new nodes (e.g., conflict detection, follow-up scheduling) without refactoring.

**Why sequential agents instead of parallel?**
The summary agent depends on all three extraction agents. Running extractions sequentially keeps the code simple. If processing speed becomes a bottleneck, extractions 1–3 can be parallelized using LangGraph's `Send` API with a single config change.
