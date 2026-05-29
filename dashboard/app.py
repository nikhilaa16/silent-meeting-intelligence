"""
Silent Meeting Intelligence — Streamlit Dashboard
==================================================

A beautiful, interactive frontend that lets users:
  1. Upload a meeting recording (drag & drop)
  2. Watch real-time processing status with live polling
  3. See structured intelligence in clean tabs
  4. Browse meeting history in the sidebar
"""
import time
from datetime import datetime
import os
from dotenv import load_dotenv

import requests
import streamlit as st

# Load API key from .env so dashboard can authenticate with the backend
load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "silent-meeting-super-secret-2025")
AUTH_HEADERS = {"X-API-Key": API_KEY}
POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 120  # 6 minutes max

st.set_page_config(
    page_title="Silent Meeting Intelligence",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Dark background */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0f0f1a 100%);
    }

    /* Main title */
    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        background: linear-gradient(135deg, #a78bfa, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    /* Cards */
    .intel-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 0.8rem;
        transition: border-color 0.2s ease;
    }

    .intel-card:hover {
        border-color: rgba(167, 139, 250, 0.3);
    }

    /* Decision card */
    .decision-card {
        background: rgba(52, 211, 153, 0.08);
        border-left: 3px solid #34d399;
        border-radius: 0 12px 12px 0;
        padding: 0.9rem 1.2rem;
        margin-bottom: 0.6rem;
        color: #e2e8f0;
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* Action item card */
    .action-card {
        background: rgba(96, 165, 250, 0.08);
        border: 1px solid rgba(96, 165, 250, 0.2);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.7rem;
    }

    .action-task {
        color: #e2e8f0;
        font-weight: 500;
        font-size: 0.95rem;
        margin-bottom: 0.5rem;
    }

    .action-meta {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
    }

    /* Question card */
    .question-card {
        background: rgba(251, 191, 36, 0.07);
        border-left: 3px solid #fbbf24;
        border-radius: 0 12px 12px 0;
        padding: 0.9rem 1.2rem;
        margin-bottom: 0.6rem;
        color: #e2e8f0;
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* Priority badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }

    .badge-high   { background: rgba(239,68,68,0.2);   color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    .badge-medium { background: rgba(251,191,36,0.2);  color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
    .badge-low    { background: rgba(52,211,153,0.2);  color: #34d399; border: 1px solid rgba(52,211,153,0.3); }
    .badge-owner  { background: rgba(167,139,250,0.2); color: #a78bfa; border: 1px solid rgba(167,139,250,0.3); }
    .badge-due    { background: rgba(96,165,250,0.2);  color: #60a5fa; border: 1px solid rgba(96,165,250,0.3); }

    /* Summary box */
    .summary-box {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(167,139,250,0.2);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        color: #cbd5e1;
        font-size: 1rem;
        line-height: 1.8;
    }

    /* Stat counters */
    .stat-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }

    .stat-box {
        flex: 1;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }

    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #a78bfa;
    }

    .stat-label {
        font-size: 0.8rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.2rem;
    }

    /* History item */
    .history-item {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: border-color 0.2s;
    }

    .history-item:hover {
        border-color: rgba(167,139,250,0.3);
    }

    /* Status dot */
    .dot-completed { color: #34d399; }
    .dot-processing { color: #fbbf24; }
    .dot-failed { color: #f87171; }

    /* Transcript box */
    .transcript-box {
        background: rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.2rem;
        color: #94a3b8;
        font-size: 0.88rem;
        line-height: 1.7;
        max-height: 300px;
        overflow-y: auto;
        font-family: 'Inter', monospace;
        white-space: pre-wrap;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: transparent;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #64748b;
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.2rem;
        font-size: 0.9rem;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(167,139,250,0.15);
        color: #a78bfa;
        border-bottom: 2px solid #a78bfa;
    }

    /* Upload area */
    .upload-hint {
        color: #475569;
        font-size: 0.85rem;
        text-align: center;
        margin-top: 0.5rem;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #475569;
    }
    .empty-icon { font-size: 3rem; margin-bottom: 0.8rem; }
    .empty-text { font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# API Helpers
# ─────────────────────────────────────────────

def api_get(path: str) -> dict | list | None:
    try:
        r = requests.get(f"{API_URL}{path}", headers=AUTH_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_post_file(path: str, file_bytes: bytes, filename: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_URL}{path}",
            files={"file": (filename, file_bytes)},
            headers=AUTH_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None


def priority_badge(priority: str) -> str:
    cls = f"badge-{priority.lower()}" if priority.lower() in ("high", "medium", "low") else "badge-medium"
    return f'<span class="badge {cls}">{priority.upper()}</span>'


def status_dot(status: str) -> str:
    icons = {"completed": "🟢", "processing": "🟡", "failed": "🔴"}
    return icons.get(status, "⚪")


# ─────────────────────────────────────────────
# Sidebar — Meeting History
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🎙️ Silent Meeting Intel")
    st.markdown("---")

    # Check backend connectivity
    health = api_get("/health")
    if health:
        st.success("✅ Backend connected", icon=None)
    else:
        st.error("❌ Backend offline\nRun: `python run_backend.py`")

    st.markdown("### 📋 Meeting History")

    meetings = api_get("/meetings") or []

    if not meetings:
        st.markdown('<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">No meetings yet.<br>Upload one to get started.</div></div>', unsafe_allow_html=True)
    else:
        # Select meeting from history
        if "selected_meeting_id" not in st.session_state:
            st.session_state.selected_meeting_id = None

        for m in meetings:
            dot = status_dot(m["status"])
            created = m.get("created_at", "")[:16].replace("T", " ") if m.get("created_at") else "—"
            label = f"{dot} {m['filename'][:28]}"
            if st.button(label, key=f"btn_{m['id']}", use_container_width=True, help=f"Created: {created}"):
                st.session_state.selected_meeting_id = m["id"]
                st.rerun()

    st.markdown("---")
    if st.button("🔄 Refresh History", use_container_width=True):
        st.rerun()


# ─────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────

st.markdown('<h1 class="main-title">🎙️ Silent Meeting Intelligence</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Upload any meeting recording. Get decisions, action items, and next steps — instantly.</p>', unsafe_allow_html=True)

# ── Upload Section ────────────────────────────────────────────────────────────

with st.container():
    upload_tab, record_tab = st.tabs(["📁 Upload File", "🎤 Record Live Meeting"])
    uploaded_file = None
    
    with upload_tab:
        uploaded_file = st.file_uploader(
            "Drop your meeting recording here",
            type=["mp3", "mp4", "wav", "m4a", "ogg", "webm"],
            help="Supports MP3, MP4, WAV, M4A, OGG, WEBM",
            key="file_uploader",
        )
        st.markdown('<p class="upload-hint">Supports MP3 · MP4 · WAV · M4A · OGG · WEBM &nbsp;|&nbsp; Max 100 MB</p>', unsafe_allow_html=True)
        
    with record_tab:
        recorded_audio = st.audio_input("Record a brief meeting note or summary directly:")
        if recorded_audio is not None:
            uploaded_file = recorded_audio
            # Ensure it has a valid filename when sent to FastAPI
            if not hasattr(uploaded_file, "name") or not uploaded_file.name:
                uploaded_file.name = f"recorded_meeting_{int(time.time())}.wav"

if uploaded_file is not None:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Analyze Meeting", use_container_width=True, type="primary"):
            with st.spinner("Uploading..."):
                response = api_post_file("/meetings/upload", uploaded_file.getvalue(), uploaded_file.name)

            if response and response.get("meeting_id"):
                st.session_state.selected_meeting_id = response["meeting_id"]
                st.rerun()

# ── Results Section ───────────────────────────────────────────────────────────

meeting_id = st.session_state.get("selected_meeting_id")

if meeting_id:
    st.markdown("---")

    # Poll until completed or failed
    placeholder = st.empty()
    poll_count = 0

    while True:
        data = api_get(f"/meetings/{meeting_id}")

        if not data:
            st.error("Could not fetch meeting data. Is the backend running?")
            break

        status = data.get("status", "processing")

        if status == "processing":
            with placeholder.container():
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.markdown("""
                        <div style="text-align:center; padding: 3rem 0;">
                            <div style="font-size:3rem; margin-bottom:1rem;">⚙️</div>
                            <div style="color:#a78bfa; font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                                Processing your meeting...
                            </div>
                            <div style="color:#64748b; font-size:0.9rem;">
                                Transcribing audio → Running 4 AI agents → Extracting intelligence
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            time.sleep(POLL_INTERVAL_SECONDS)
            poll_count += 1
            if poll_count > MAX_POLL_ATTEMPTS:
                st.warning("Processing is taking longer than expected. Please refresh the page.")
                break
            continue

        # Completed or failed — clear the spinner
        placeholder.empty()

        if status == "failed":
            st.error(f"❌ Processing failed: {data.get('error_message', 'Unknown error')}")
            break

        # ── Render Results ────────────────────────────────────────────────

        filename = data.get("filename", "Meeting")
        decisions = data.get("decisions") or []
        action_items = data.get("action_items") or []
        open_questions = data.get("open_questions") or []
        summary = data.get("summary") or ""
        transcript = data.get("transcript") or ""
        conflicts = data.get("conflicts") or []

        # Header
        st.markdown(f"### 📄 {filename}")

        # Stats row — show conflicts count in red if any found
        conflict_color = "#f87171" if conflicts else "#a78bfa"
        st.markdown(f"""
        <div class="stat-row">
            <div class="stat-box">
                <div class="stat-number">{len(decisions)}</div>
                <div class="stat-label">Decisions</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len(action_items)}</div>
                <div class="stat-label">Action Items</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len(open_questions)}</div>
                <div class="stat-label">Open Questions</div>
            </div>
            <div class="stat-box">
                <div class="stat-number" style="color:{conflict_color}">{len(conflicts)}</div>
                <div class="stat-label">Conflicts</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Tabs
        tab_summary, tab_decisions, tab_actions, tab_questions, tab_conflicts, tab_email, tab_transcript = st.tabs([
            "📋 Summary",
            f"✅ Decisions ({len(decisions)})",
            f"🎯 Action Items ({len(action_items)})",
            f"❓ Open Questions ({len(open_questions)})",
            f"⚠️ Conflicts ({len(conflicts)})" if conflicts else "✅ No Conflicts",
            "📧 Follow-up Email",
            "📝 Transcript",
        ])

        # ── Tab: Summary ──────────────────────────────────────────────
        with tab_summary:
            st.markdown("<br>", unsafe_allow_html=True)
            if summary:
                st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)
            else:
                st.info("No summary generated.")

        # ── Tab: Decisions ────────────────────────────────────────────
        with tab_decisions:
            st.markdown("<br>", unsafe_allow_html=True)
            if decisions:
                for i, decision in enumerate(decisions, 1):
                    st.markdown(f'<div class="decision-card">✅ {decision}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">🤷</div><div class="empty-text">No decisions were finalized in this meeting.</div></div>', unsafe_allow_html=True)

        # ── Tab: Action Items ─────────────────────────────────────────
        with tab_actions:
            st.markdown("<br>", unsafe_allow_html=True)
            if action_items:
                priority_order = {"high": 0, "medium": 1, "low": 2}
                sorted_items = sorted(action_items, key=lambda x: priority_order.get(x.get("priority", "medium").lower(), 1))

                for item in sorted_items:
                    task = item.get("task", "Unknown task")
                    owner = item.get("owner", "Unassigned")
                    deadline = item.get("deadline") or "Not set"
                    priority = item.get("priority", "medium")

                    st.markdown(f"""
                    <div class="action-card">
                        <div class="action-task">🎯 {task}</div>
                        <div class="action-meta">
                            <span class="badge badge-owner">👤 {owner}</span>
                            <span class="badge badge-due">📅 {deadline}</span>
                            {priority_badge(priority)}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">✨</div><div class="empty-text">No action items found.</div></div>', unsafe_allow_html=True)

        # ── Tab: Open Questions ───────────────────────────────────────
        with tab_questions:
            st.markdown("<br>", unsafe_allow_html=True)
            if open_questions:
                for question in open_questions:
                    st.markdown(f'<div class="question-card">❓ {question}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">🎉</div><div class="empty-text">All questions were resolved in this meeting!</div></div>', unsafe_allow_html=True)

        # ── Tab: Conflicts ────────────────────────────────────────────
        with tab_conflicts:
            st.markdown("<br>", unsafe_allow_html=True)
            if conflicts:
                st.markdown("""
                <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.25);
                     border-radius:12px; padding:1rem 1.2rem; margin-bottom:1.2rem;">
                    <div style="color:#f87171; font-weight:600; margin-bottom:0.3rem;">Contradictions Detected</div>
                    <div style="color:#94a3b8; font-size:0.9rem;">
                        These new decisions may contradict decisions made in previous meetings.
                        Review carefully before proceeding.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                for c in conflicts:
                    st.markdown(f"""
                    <div style="background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.2);
                         border-radius:12px; padding:1.1rem 1.3rem; margin-bottom:0.8rem;">
                        <div style="color:#fca5a5; font-size:0.82rem; text-transform:uppercase;
                             letter-spacing:0.05em; margin-bottom:0.6rem; font-weight:600;">
                            Conflict Detected
                        </div>
                        <div style="color:#e2e8f0; font-weight:500; margin-bottom:0.4rem;">
                            New: {c.get('new_decision', '')}
                        </div>
                        <div style="color:#94a3b8; font-size:0.9rem; margin-bottom:0.4rem;">
                            Contradicts: {c.get('past_decision', '')}
                            <span style='color:#475569'>(from {c.get('past_meeting', 'a past meeting')})</span>
                        </div>
                        <div style="color:#fbbf24; font-size:0.88rem; font-style:italic;">
                            {c.get('explanation', '')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">✅</div><div class="empty-text">No conflicts with past meetings.<br>All decisions are consistent.</div></div>', unsafe_allow_html=True)

        # ── Tab: Transcript ────────────────────────────────────────────
        with tab_transcript:
            st.markdown("<br>", unsafe_allow_html=True)
            if transcript:
                st.markdown(f'<div class="transcript-box">{transcript}</div>', unsafe_allow_html=True)
                st.markdown(f"<br><small style='color:#475569'>Word count: ~{len(transcript.split())} words</small>", unsafe_allow_html=True)
            else:
                st.info("Transcript not available.")

        # ── Tab: Follow-up Email ──────────────────────────────────────
        with tab_email:
            st.markdown("<br>", unsafe_allow_html=True)
            email_draft = data.get("email_draft") or ""
            if email_draft:
                st.code(email_draft, language="markdown")
                st.markdown("""
                <small style='color:#64748b'>
                    💡 You can copy the raw markdown email above and send it directly to your client or team.
                </small>
                """, unsafe_allow_html=True)
            else:
                st.info("No email draft generated for this meeting.")

        break  # Exit polling loop — we have results

else:
    # No meeting selected — show welcome screen and RAG search
    st.markdown("### 🔍 Search Past Meetings (Semantic RAG)")
    search_query = st.text_input(
        "Ask a question about any past meeting:",
        placeholder="e.g. 'What did we decide about the database?' or 'Who owns the setup tasks?'",
    )
    if search_query:
        with st.spinner("Searching transcripts..."):
            try:
                r = requests.get(
                    f"{API_URL}/meetings/search",
                    params={"query": search_query},
                    headers=AUTH_HEADERS,
                    timeout=20,
                )
                if r.status_code == 200:
                    result = r.json()
                    answer = result.get("answer", "No answer could be generated.")
                    sources = result.get("sources") or []

                    st.markdown("#### 🤖 Answer")
                    st.info(answer)

                    if sources:
                        with st.expander("📄 Citations & Context"):
                            for idx, src in enumerate(sources, 1):
                                st.markdown(f"**Source #{idx} — Meeting: {src['filename']} ({src['date']})**")
                                st.markdown(f"*{src['snippet']}*")
                                st.markdown("---")
                else:
                    st.error(f"Search failed: {r.status_code} - {r.text}")
            except Exception as err:
                st.error(f"Error querying search endpoint: {err}")

    st.markdown("---")
    
    if not meetings:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 2rem;">
            <div style="font-size:4rem; margin-bottom:1.5rem;">🎙️</div>
            <h2 style="color:#e2e8f0; font-weight:600; margin-bottom:0.8rem;">
                Never lose a meeting decision again
            </h2>
            <p style="color:#64748b; font-size:1rem; max-width:500px; margin:0 auto 2rem; line-height:1.7;">
                Upload any meeting recording above. Our 4-agent AI pipeline will extract 
                every decision, action item, and open question — in under 2 minutes.
            </p>
            <div style="display:flex; gap:2rem; justify-content:center; flex-wrap:wrap; margin-top:1.5rem;">
                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:1.2rem; width:160px;">
                    <div style="font-size:1.8rem;">✅</div>
                    <div style="color:#e2e8f0; font-weight:500; margin:0.4rem 0 0.2rem;">Decisions</div>
                    <div style="color:#64748b; font-size:0.82rem;">What was agreed</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:1.2rem; width:160px;">
                    <div style="font-size:1.8rem;">🎯</div>
                    <div style="color:#e2e8f0; font-weight:500; margin:0.4rem 0 0.2rem;">Action Items</div>
                    <div style="color:#64748b; font-size:0.82rem;">Who does what</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:1.2rem; width:160px;">
                    <div style="font-size:1.8rem;">❓</div>
                    <div style="color:#e2e8f0; font-weight:500; margin:0.4rem 0 0.2rem;">Open Questions</div>
                    <div style="color:#64748b; font-size:0.82rem;">What's unresolved</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
