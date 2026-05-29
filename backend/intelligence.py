"""
LangGraph Intelligence Pipeline
================================

This is the brain of the project. A 4-node LangGraph pipeline that
transforms a raw meeting transcript into structured, actionable intelligence.

Pipeline flow:
  transcript
      │
      ▼
  [extract_decisions]     → What was agreed upon?
      │
      ▼
  [extract_action_items]  → Who committed to what, by when?
      │
      ▼
  [extract_open_questions]→ What was left unresolved?
      │
      ▼
  [generate_summary]      → Executive summary of the whole meeting
      │
      ▼
    END

Why LangGraph over plain LangChain?
- Explicit state machine → we always know what step we're on
- Each node is independently testable
- Easy to add new nodes later (e.g. conflict detection, follow-up scheduler)
- Industry standard for production agentic pipelines (appears in 90%+ of AI job postings)
"""
import json
import logging
from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from .config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# State Definition
# ─────────────────────────────────────────────

class MeetingState(TypedDict):
    """
    The shared state passed between every node in the graph.
    Each node reads from and writes to this state.
    """
    transcript: str
    decisions: list[str]
    action_items: list[dict]
    open_questions: list[str]
    summary: str
    email_draft: str
    speakers: list[str]   # detected speaker labels e.g. ["Speaker A", "Speaker B"]
    has_diarization: bool # True when transcript has [Speaker X 00:00:00] format
    error: Optional[str]


# ─────────────────────────────────────────────
# Speaker Diarization Helper
# ─────────────────────────────────────────────

def _detect_speakers(transcript: str) -> tuple[bool, list[str]]:
    """
    Detect whether the transcript has speaker diarization labels.
    Returns (has_diarization, list_of_unique_speakers).

    Expects format: [Speaker A 00:01:23] text...
    """
    import re
    pattern = r'\[Speaker ([A-Z]) \d{2}:\d{2}\]'
    matches = re.findall(pattern, transcript)
    if not matches:
        return False, []
    unique = sorted(set(f"Speaker {s}" for s in matches))
    return True, unique


# ─────────────────────────────────────────────
# LLM Factory
# ─────────────────────────────────────────────

def _get_llm() -> ChatGroq:
    """Return a configured Groq LLM instance with retries on rate limits."""
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_LLM_MODEL,
        temperature=0,          # Deterministic — we want consistent extractions
        max_tokens=2048,
        max_retries=10,         # Automatically retries on 429 rate limits / concurrency limits
    )


def _safe_json_parse(text: str, fallback_key: str) -> list:
    """
    Safely parse JSON from LLM response.
    LLMs sometimes wrap JSON in markdown code fences — this handles that.
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])

    try:
        data = json.loads(cleaned)
        # Handle both {"key": [...]} and [...] formats
        if isinstance(data, dict):
            return data.get(fallback_key, [])
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON from LLM response: {text[:200]}")

    return []


# ─────────────────────────────────────────────
# Node 1: Extract Decisions
# ─────────────────────────────────────────────

def extract_decisions(state: MeetingState) -> MeetingState:
    """
    Identifies all decisions that were finalized in the meeting.
    Speaker-aware: uses speaker labels when available to credit decisions.
    """
    llm = _get_llm()

    speaker_note = ""
    if state.get("has_diarization") and state.get("speakers"):
        speaker_list = ", ".join(state["speakers"])
        speaker_note = f"""
NOTE: This transcript includes speaker labels in the format [Speaker X HH:MM].
Speakers detected: {speaker_list}
When extracting decisions, include the speaker who stated the decision.
"""

    prompt = f"""You are an expert meeting analyst specializing in decision extraction.
{speaker_note}
Analyze the following meeting transcript and extract ALL decisions that were made.

A DECISION is:
✅ Something explicitly agreed upon ("We will...", "It's decided that...", "Let's go with...")
✅ A choice that was finalized between options
✅ A confirmed plan, approach, or direction

NOT a decision:
❌ Ideas that were only suggested but not confirmed
❌ Questions or uncertainties
❌ Action items (tasks to be done)

Meeting Transcript:
\"\"\"
{state['transcript']}
\"\"\"

Return ONLY a JSON object in this exact format:
{{
  "decisions": [
    "Decision 1 written as a clear, complete sentence",
    "Decision 2 written as a clear, complete sentence"
  ]
}}

If no decisions were made, return: {{"decisions": []}}
Return ONLY the JSON. No explanation, no markdown."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        decisions = _safe_json_parse(response.content, "decisions")
        return {**state, "decisions": decisions}
    except Exception as e:
        logger.error(f"Decision extraction failed: {e}")
        return {**state, "decisions": [], "error": str(e)}


# ─────────────────────────────────────────────
# Node 2: Extract Action Items
# ─────────────────────────────────────────────

def extract_action_items(state: MeetingState) -> MeetingState:
    """
    Extracts all tasks with owners, deadlines, and priorities.
    Speaker-aware: uses actual speaker names from diarization as owners.
    """
    llm = _get_llm()

    speaker_note = ""
    if state.get("has_diarization") and state.get("speakers"):
        speaker_list = ", ".join(state["speakers"])
        speaker_note = f"""
NOTE: This transcript has speaker diarization labels in [Speaker X HH:MM] format.
Speakers: {speaker_list}
IMPORTANT: Use the exact speaker label (e.g. "Speaker A", "Speaker B") as the owner
when a specific person committed to a task. Use "Unassigned" only when it's truly unclear.
Also extract the timestamp from the transcript line for each action item.
"""

    deadline_note = """
For deadlines: Convert relative expressions to be explicit:
- "by Friday" → keep as "Friday"
- "next week" → keep as "next week"
- "in 3 days" → keep as "in 3 days"
- Specific dates → keep exact
"""

    prompt = f"""You are an expert meeting analyst specializing in action item extraction.
{speaker_note}{deadline_note}
Analyze the following meeting transcript and extract ALL action items (tasks that someone committed to doing).

An ACTION ITEM is:
✅ A specific task someone agreed to do
✅ Something with a responsible person (or that needs one assigned)
✅ Work that needs to happen after the meeting

Tricky cases:
- "Can you handle the API?" → the LISTENER is the owner, not the speaker asking
- "I'll fix the bug" → the speaker is the owner
- "Someone needs to update the docs" → Unassigned

For each action item extract:
- task: Specific actionable sentence
- owner: Speaker label or name ("Speaker A", "Speaker B", or "Unassigned")
- deadline: When due, or null
- priority: "high", "medium", or "low"
- timestamp: HH:MM from transcript if available, or null

Meeting Transcript:
\"\"\"
{state['transcript']}
\"\"\"

Return ONLY a JSON object:
{{
  "action_items": [
    {{
      "task": "Send the updated proposal to the client",
      "owner": "Speaker A",
      "deadline": "Friday",
      "priority": "high",
      "timestamp": "00:05"
    }},
    {{
      "task": "Update the database schema documentation",
      "owner": "Unassigned",
      "deadline": null,
      "priority": "low",
      "timestamp": null
    }}
  ]
}}

If no action items exist, return: {{"action_items": []}}
Return ONLY the JSON. No explanation, no markdown."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        action_items = _safe_json_parse(response.content, "action_items")
        return {**state, "action_items": action_items}
    except Exception as e:
        logger.error(f"Action item extraction failed: {e}")
        return {**state, "action_items": [], "error": str(e)}


# ─────────────────────────────────────────────
# Node 3: Extract Open Questions
# ─────────────────────────────────────────────

def extract_open_questions(state: MeetingState) -> MeetingState:
    """
    Identifies unresolved questions and issues that need follow-up.
    Speaker-aware: notes which speaker raised each question.
    """
    llm = _get_llm()

    speaker_note = ""
    if state.get("has_diarization") and state.get("speakers"):
        speaker_list = ", ".join(state["speakers"])
        speaker_note = f"""
NOTE: This transcript has speaker diarization. Speakers: {speaker_list}
When extracting open questions, include WHO raised it (e.g. "Speaker A: What is the budget?")
"""

    prompt = f"""You are an expert meeting analyst specializing in identifying unresolved issues.
{speaker_note}
Analyze the following meeting transcript and extract ALL open questions and unresolved issues.

An OPEN QUESTION is:
✅ A question raised but NOT answered in the meeting
✅ An issue discussed but no conclusion was reached
✅ A disagreement that remains unresolved
✅ Something needing more information before a decision can be made

NOT an open question:
❌ Questions asked AND answered in the meeting
❌ Rhetorical questions
❌ Questions that became action items or decisions

Meeting Transcript:
\"\"\"
{state['transcript']}
\"\"\"

Return ONLY a JSON object:
{{
  "open_questions": [
    "Speaker A: What is the budget for the new marketing campaign?",
    "Who will handle client onboarding after the handoff?"
  ]
}}

If everything was resolved, return: {{"open_questions": []}}
Return ONLY the JSON. No explanation, no markdown."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        open_questions = _safe_json_parse(response.content, "open_questions")
        return {**state, "open_questions": open_questions}
    except Exception as e:
        logger.error(f"Open question extraction failed: {e}")
        return {**state, "open_questions": [], "error": str(e)}


# ─────────────────────────────────────────────
# Node 4: Generate Summary
# ─────────────────────────────────────────────

def generate_summary(state: MeetingState) -> MeetingState:
    """
    Synthesizes everything into a concise executive summary.
    Uses all previously extracted intelligence for context.
    """
    llm = _get_llm()

    decisions_text = "\n".join(f"• {d}" for d in state["decisions"]) or "None"
    action_items_text = "\n".join(
        f"• [{item.get('owner', 'Unassigned')}] {item.get('task', '')} "
        f"(Priority: {item.get('priority', 'medium')}, Due: {item.get('deadline', 'Not set')})"
        for item in state["action_items"]
    ) or "None"
    questions_text = "\n".join(f"• {q}" for q in state["open_questions"]) or "None"

    prompt = f"""You are an expert meeting analyst.

Write a concise, professional executive summary of this meeting in 3-5 sentences.

The summary should cover:
1. What the meeting was about (main topic/purpose)
2. Key outcomes and what was accomplished
3. What needs to happen next (next steps)

Use this information:

TRANSCRIPT:
\"\"\"
{state['transcript'][:2000]}{"..." if len(state['transcript']) > 2000 else ""}
\"\"\"

DECISIONS MADE:
{decisions_text}

ACTION ITEMS:
{action_items_text}

OPEN QUESTIONS:
{questions_text}

Write ONLY the summary paragraph. Professional tone. No bullet points. No headings. Just clean prose."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return {**state, "summary": response.content.strip()}
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return {**state, "summary": "Summary generation failed.", "error": str(e)}


# ─────────────────────────────────────────────
# Node 5: Generate Follow-up Email Draft
# ─────────────────────────────────────────────

def generate_email_draft(state: MeetingState) -> MeetingState:
    """
    Drafts a professional, friendly client follow-up email
    based on the extracted decisions, summary, and action items.
    """
    llm = _get_llm()

    decisions_text = "\n".join(f"• {d}" for d in state["decisions"]) or "None"
    action_items_text = "\n".join(
        f"• [{item.get('owner', 'Unassigned')}] {item.get('task', '')} "
        f"(Due: {item.get('deadline', 'Not set')})"
        for item in state["action_items"]
    ) or "None"
    questions_text = "\n".join(f"• {q}" for q in state["open_questions"]) or "None"

    prompt = f"""You are an expert executive assistant.

Write a professional follow-up email to send to the client or team after this meeting.

The email must include:
1. A polite, warm opening thank-you note.
2. A brief, 2-sentence summary of the meeting.
3. A list of key decisions made.
4. A clear table or list of action items with who owns them and when they are due.
5. Open questions that need follow-up (if any).
6. A warm, professional sign-off.

Use this context:
SUMMARY: {state['summary']}
DECISIONS:
{decisions_text}
ACTION ITEMS:
{action_items_text}
OPEN QUESTIONS:
{questions_text}

Write ONLY the complete email text (including Subject line at the very top: "Subject: ..."). Do not add any extra explanations or wrapping markdown text outside the email format."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return {**state, "email_draft": response.content.strip()}
    except Exception as e:
        logger.error(f"Email drafting failed: {e}")
        return {**state, "email_draft": "Email draft generation failed.", "error": str(e)}


# ─────────────────────────────────────────────
# Graph Builder
# ─────────────────────────────────────────────

def build_intelligence_graph():
    """
    Construct and compile the LangGraph pipeline.

    Graph structure:
        extract_decisions → extract_action_items → extract_open_questions → generate_summary → generate_email → END
    """
    graph = StateGraph(MeetingState)

    # Register nodes
    graph.add_node("extract_decisions", extract_decisions)
    graph.add_node("extract_action_items", extract_action_items)
    graph.add_node("extract_open_questions", extract_open_questions)
    graph.add_node("generate_summary", generate_summary)
    graph.add_node("generate_email", generate_email_draft)

    # Define the sequential flow
    graph.set_entry_point("extract_decisions")
    graph.add_edge("extract_decisions", "extract_action_items")
    graph.add_edge("extract_action_items", "extract_open_questions")
    graph.add_edge("extract_open_questions", "generate_summary")
    graph.add_edge("generate_summary", "generate_email")
    graph.add_edge("generate_email", END)

    return graph.compile()


# ─────────────────────────────────────────────
# Conflict Detection (Cross-Meeting)
# ─────────────────────────────────────────────

def detect_conflicts(new_decisions: list[str], past_decisions: list[dict]) -> list[dict]:
    """
    Cross-meeting conflict detection — the most novel feature.

    Compares new decisions from the current meeting against ALL decisions
    from previous meetings. Uses the LLM to detect semantic contradictions,
    not just keyword matching.

    Example:
      Past decision:   "We will use PostgreSQL as our database"
      New decision:    "We have decided to migrate to MongoDB"
      → CONFLICT DETECTED

    Args:
        new_decisions:  Decisions from the current meeting.
        past_decisions: List of dicts [{decision, meeting_id, filename, created_at}]
                        from all previous meetings in the database.

    Returns:
        List of conflict dicts: [{new_decision, past_decision, past_meeting, explanation}]
    """
    if not new_decisions or not past_decisions:
        return []

    llm = _get_llm()

    # Format past decisions for the prompt
    past_text = "\n".join(
        f"[Meeting: {p.get('filename', 'Unknown')} | Date: {p.get('created_at', 'Unknown')}]\n  Decision: {p.get('decision', '')}"
        for p in past_decisions
    )

    new_text = "\n".join(f"- {d}" for d in new_decisions)

    prompt = f"""You are an expert meeting analyst specializing in detecting contradictions.

Compare the NEW decisions from a recent meeting against PAST decisions from previous meetings.
Identify any contradictions, reversals, or conflicts between them.

A CONFLICT exists when:
- A new decision directly reverses or contradicts a past decision
- A new decision makes a past decision impossible to execute
- A new decision changes something that was previously finalized

NOT a conflict:
- A new decision that builds on or extends a past decision
- A new decision in a completely different domain
- A past decision that was clearly superseded intentionally

NEW DECISIONS (from current meeting):
{new_text}

PAST DECISIONS (from previous meetings):
{past_text}

Return ONLY a JSON object:
{{
  "conflicts": [
    {{
      "new_decision": "exact new decision that conflicts",
      "past_decision": "exact past decision it contradicts",
      "past_meeting": "filename of the past meeting",
      "explanation": "one sentence explaining why this is a conflict"
    }}
  ]
}}

If no conflicts exist, return: {{"conflicts": []}}
Return ONLY the JSON. No explanation, no markdown."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        conflicts = _safe_json_parse(response.content, "conflicts")
        return conflicts if isinstance(conflicts, list) else []
    except Exception as e:
        logger.error(f"Conflict detection failed: {e}")
        return []


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def analyze_meeting(transcript: str) -> dict:
    """
    Run the full 5-agent intelligence pipeline on a meeting transcript.

    Automatically detects speaker diarization — if the transcript has
    [Speaker A 00:01:23] labels, all nodes become speaker-aware.

    Args:
        transcript: Raw text transcript of the meeting.

    Returns:
        dict with keys: decisions, action_items, open_questions, summary, email_draft, speakers, error
    """
    # Auto-detect speaker diarization from transcript format
    has_diarization, speakers = _detect_speakers(transcript)
    if has_diarization:
        logger.info(f"Speaker diarization detected: {speakers}")
    else:
        logger.info("No speaker diarization — using plain transcript mode")

    initial_state: MeetingState = {
        "transcript": transcript,
        "decisions": [],
        "action_items": [],
        "open_questions": [],
        "summary": "",
        "email_draft": "",
        "speakers": speakers,
        "has_diarization": has_diarization,
        "error": None,
    }

    # Parallelize the 4 independent LLM agents (decisions, action items, open questions, summary)
    import concurrent.futures
    logger.info("Running 4 independent extraction agents in parallel...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_decisions = executor.submit(extract_decisions, initial_state)
        future_action_items = executor.submit(extract_action_items, initial_state)
        future_open_questions = executor.submit(extract_open_questions, initial_state)
        future_summary = executor.submit(generate_summary, initial_state)

        state_decisions = future_decisions.result()
        state_action_items = future_action_items.result()
        state_open_questions = future_open_questions.result()
        state_summary = future_summary.result()

    # Merge results into a combined state
    merged_state = initial_state.copy()
    merged_state["decisions"] = state_decisions.get("decisions", [])
    merged_state["action_items"] = state_action_items.get("action_items", [])
    merged_state["open_questions"] = state_open_questions.get("open_questions", [])
    merged_state["summary"] = state_summary.get("summary", "")

    # Run the dependent agent (email draft) sequentially using the merged state
    logger.info("Running follow-up email draft generator...")
    final_state = generate_email_draft(merged_state)
    return final_state


# ─────────────────────────────────────────────
# Lexical RAG Search (TF-IDF) (Cross-Meeting QA)
# ─────────────────────────────────────────────

def semantic_search_meetings(query: str, past_meetings: list) -> dict:
    """
    Perform a Lexical RAG Search (TF-IDF) across all completed meeting transcripts.

    Args:
        query: User search query or question.
        past_meetings: List of database records with filename, created_at, transcript, summary.

    Returns:
        dict containing:
            - answer: Synthesized answer to the query with citations.
            - sources: List of source chunks/meetings found.
    """
    if not past_meetings or not query.strip():
        return {
            "answer": "No past meetings available to search.",
            "sources": []
        }

    # 1. Chunk all transcripts into paragraphs
    import re
    import math
    chunks = []
    for meeting in past_meetings:
        # Check if meeting has a transcript (could be direct model dict or DB object)
        transcript = getattr(meeting, "transcript", None) or meeting.get("transcript")
        if not transcript:
            continue
        
        filename = getattr(meeting, "filename", None) or meeting.get("filename") or "Unknown"
        created_at = getattr(meeting, "created_at", None) or meeting.get("created_at")
        meeting_id = getattr(meeting, "id", None) or meeting.get("id")

        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', transcript) if len(p.strip()) > 30]
        for idx, para in enumerate(paragraphs):
            chunks.append({
                "meeting_id": meeting_id,
                "filename": filename,
                "date": str(created_at)[:10] if created_at else "Unknown",
                "paragraph_idx": idx,
                "text": para
            })

    if not chunks:
        return {
            "answer": "No searchable text chunks found in past meetings.",
            "sources": []
        }

    # 2. Score chunks using simple Python-only TF-IDF/keyword ranking
    terms = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 2]
    if not terms:
        top_chunks = chunks[:5]
    else:
        scored_chunks = []
        for chunk in chunks:
            score = 0
            text_lower = chunk["text"].lower()
            for term in terms:
                count = text_lower.count(term)
                if count > 0:
                    tf = 1 + math.log(count)
                    score += tf
            if score > 0:
                scored_chunks.append((score, chunk))
        
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [item[1] for item in scored_chunks[:5]]

    if not top_chunks:
        return {
            "answer": f"No relevant information found matching your query: '{query}'.",
            "sources": []
        }

    # 3. Call LLaMA to synthesize the final answer from retrieved chunks
    llm = _get_llm()

    context_str = "\n\n".join(
        f"[Source #{i+1} | Meeting: {chunk['filename']} | Date: {chunk['date']}]\nSnippet: \"{chunk['text']}\""
        for i, chunk in enumerate(top_chunks)
    )

    prompt = f"""You are a helpful AI assistant. You have access to snippets of transcripts from previous business meetings.

Use the provided meeting snippets to answer the user's question.

Rules:
1. Provide a direct, comprehensive, and professional answer.
2. You must cite your sources inline using [Source #X] or referencing the meeting name/date.
3. Base your answer strictly on the snippets provided. If the snippets do not contain enough information, state that clearly.

USER QUESTION: "{query}"

MEETING SNIPPETS:
{context_str}

Return ONLY the final synthesized answer with proper citations. Do not write any wrapping JSON or XML. Just clean markdown prose."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return {
            "answer": response.content.strip(),
            "sources": [
                {
                    "filename": c["filename"],
                    "date": c["date"],
                    "snippet": c["text"]
                }
                for c in top_chunks
            ]
        }
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return {
            "answer": f"An error occurred while answering your query: {str(e)}",
            "sources": []
        }


# ─────────────────────────────────────────────
# Meeting-Specific Chatbot Helper
# ─────────────────────────────────────────────

def chat_with_meeting_helper(transcript: str, question: str, history: list[dict]) -> str:
    """
    Generate a chatbot response based on a specific meeting transcript and message history.

    Args:
        transcript: Full text transcript of the target meeting.
        question: Latest user message/question.
        history: Message history list of dicts [{"role": "user"|"assistant", "content": str}]

    Returns:
        String AI response content.
    """
    if not transcript:
        return "This meeting has no transcript. Cannot answer questions."

    llm = _get_llm()

    messages = [
        SystemMessage(content=f"""You are a helpful AI meeting assistant.
You have access to the complete transcript of this specific meeting recording.
Answer the user's questions truthfully and professionally based ONLY on the transcript context.
If the transcript does not contain the information requested, state politely: "I couldn't find that mentioned in this meeting."

Meeting Transcript:
\"\"\"
{transcript}
\"\"\"
""")
    ]

    # Re-inject conversation history
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    # Append current message
    messages.append(HumanMessage(content=question))

    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        logger.error(f"Meeting chatbot call failed: {e}")
        return f"An error occurred while generating response: {str(e)}"
