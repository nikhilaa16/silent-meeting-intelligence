"""
test_pipeline.py — End-to-end pipeline test using a mock diarized transcript.

Simulates what happens AFTER AssemblyAI diarizes a real meeting audio.
Tests all 5 LangGraph nodes + conflict detection + RAG search.

Run: python test_pipeline.py
"""

import sys
import json

# Make sure we can import the backend package
sys.path.insert(0, ".")

# Reconfigure stdout/stderr to use UTF-8 to prevent emoji errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from backend.intelligence import analyze_meeting, detect_conflicts, semantic_search_meetings

# ─────────────────────────────────────────────
# Mock Meeting 1 — Sprint Planning
# Simulates AssemblyAI diarized output
# ─────────────────────────────────────────────

MOCK_TRANSCRIPT_1 = """
[Speaker A 00:00] Alright everyone, let's kick off the sprint planning for Q3. Thanks for joining.
[Speaker B 00:08] Sure, I've reviewed the backlog. I think we should prioritize the authentication module first.
[Speaker A 00:15] Agreed. We've decided to implement JWT-based authentication for the user login flow.
[Speaker C 00:22] That works for me. I'll own the JWT implementation and have it ready by next Friday.
[Speaker B 00:30] Great. What about the database? We really need to finalise which one we're going with.
[Speaker A 00:37] We've decided to go with PostgreSQL as our primary database. No more debate on that.
[Speaker C 00:45] Good call. I'll set up the PostgreSQL schema and Docker config by Wednesday.
[Speaker B 00:52] I'll write the API endpoints for user registration and login. Can you review my PRs, Speaker A?
[Speaker A 01:00] Yes, I'll do code reviews every Tuesday and Thursday.
[Speaker C 01:08] What about the frontend? Has anyone started on that?
[Speaker B 01:12] Not yet. That's still undecided — we haven't picked React or Vue yet.
[Speaker A 01:18] Let's leave that for next meeting. We need more time to evaluate both options.
[Speaker C 01:25] Also, what's the deployment strategy? Are we going with AWS or just Render for now?
[Speaker A 01:30] Good question. We haven't decided that yet. Someone needs to research deployment options and present a comparison next week.
[Speaker B 01:40] I can do that research. I'll compare AWS, Render, and Railway and send a summary by Monday.
[Speaker A 01:48] Perfect. Let's also decide on the API structure — we're going with RESTful over GraphQL. That's final.
[Speaker C 01:55] Agreed. RESTful it is. I'll draft the API documentation template this week.
[Speaker B 02:03] One more thing — the testing strategy. Are we writing unit tests or just integration tests?
[Speaker A 02:10] Both. We've decided to use pytest for all backend testing with at least 80% code coverage.
[Speaker C 02:18] I don't think 80% is realistic for the first sprint honestly.
[Speaker B 02:22] I agree with Speaker C, that might slow us down significantly.
[Speaker A 02:28] Fair point. Let's revisit the coverage target in our next standup. It's not finalized.
[Speaker C 02:35] What's the deadline for the whole MVP?
[Speaker A 02:40] The MVP needs to be ready by August 15th. That's a hard deadline from the client.
[Speaker B 02:48] Okay. I'll make sure all my deliverables are done by August 10th to give buffer time.
[Speaker A 02:55] Perfect. Let's wrap up. To summarize — JWT auth, PostgreSQL confirmed, RESTful API confirmed. Open items are frontend framework and deployment strategy.
[Speaker C 03:02] Sounds good. Talk Thursday!
""".strip()


# ─────────────────────────────────────────────
# Mock Meeting 2 — Follow-up (creates a conflict!)
# ─────────────────────────────────────────────

MOCK_TRANSCRIPT_2 = """
[Speaker A 00:00] Quick sync everyone. I wanted to revisit the database decision from last sprint planning.
[Speaker B 00:07] Yeah, I've been doing some research. I think we should actually switch to MongoDB for better flexibility with our schema.
[Speaker A 00:15] Hmm. The client also mentioned they have existing MongoDB infrastructure. We've decided to migrate to MongoDB instead of PostgreSQL.
[Speaker C 00:24] What? We literally just decided PostgreSQL last week. Speaker C has already started the schema.
[Speaker B 00:31] I know, but the client requirements changed. MongoDB makes more sense now.
[Speaker A 00:37] The decision is made. We're going with MongoDB. Speaker C, please stop the PostgreSQL work.
[Speaker C 00:44] Okay. I'll redo the schema design for MongoDB. Can I have until next Wednesday?
[Speaker A 00:50] Yes, Wednesday is fine. Also, we've decided to go with React for the frontend — the team evaluated both and React won.
[Speaker B 00:58] Finally! I'll start the React project setup today and have the base structure done by Friday.
[Speaker A 01:05] Great. Any other blockers?
[Speaker C 01:08] The deployment research from Speaker B — did that happen?
[Speaker B 01:12] Yes, I'll send it this afternoon. I recommend Railway — it's the simplest for our stack.
[Speaker A 01:18] We've decided to use Railway for deployment. That's confirmed.
[Speaker B 01:23] Perfect. I'll set up the Railway project and CI/CD pipeline by end of week.
[Speaker A 01:28] Alright, quick meeting done. MongoDB confirmed, React confirmed, Railway confirmed.
""".strip()


# ─────────────────────────────────────────────
# Run Tests
# ─────────────────────────────────────────────

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def check(label, value):
    ok = bool(value)
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}: {value if not isinstance(value, list) else f'{len(value)} items found'}")
    return ok


def run_tests():
    results = {"passed": 0, "failed": 0}

    # ── TEST 1: Meeting 1 Pipeline ────────────────────────────────
    separator("TEST 1 — Sprint Planning Meeting (Diarized)")
    print("  Running 5-agent LangGraph pipeline on Meeting 1...")
    result1 = analyze_meeting(MOCK_TRANSCRIPT_1)

    print("\n  📋 Raw pipeline output:")
    print(f"  - has_diarization : {result1.get('has_diarization')}")
    print(f"  - speakers        : {result1.get('speakers')}")
    print(f"  - decisions       : {len(result1.get('decisions', []))} items")
    print(f"  - action_items    : {len(result1.get('action_items', []))} items")
    print(f"  - open_questions  : {len(result1.get('open_questions', []))} items")
    print(f"  - summary         : {'✅ Generated' if result1.get('summary') else '❌ Missing'}")
    print(f"  - email_draft     : {'✅ Generated' if result1.get('email_draft') else '❌ Missing'}")

    print("\n  🎯 DECISIONS:")
    for d in result1.get("decisions", []):
        print(f"    • {d}")

    print("\n  ✅ ACTION ITEMS:")
    for item in result1.get("action_items", []):
        ts = item.get("timestamp", "")
        print(f"    • [{item.get('priority','').upper()}] {item.get('task')} → Owner: {item.get('owner')} | Due: {item.get('deadline')} {f'| @{ts}' if ts else ''}")

    print("\n  ❓ OPEN QUESTIONS:")
    for q in result1.get("open_questions", []):
        print(f"    • {q}")

    print("\n  📝 SUMMARY:")
    print(f"    {result1.get('summary', 'N/A')[:300]}...")

    # Assertions
    separator("TEST 1 — Assertions")
    t = [
        check("Diarization detected", result1.get("has_diarization")),
        check("Speakers found", result1.get("speakers")),
        check("Decisions extracted", result1.get("decisions")),
        check("Action items extracted", result1.get("action_items")),
        check("Open questions found", result1.get("open_questions")),
        check("Summary generated", result1.get("summary")),
        check("Email draft generated", result1.get("email_draft")),
    ]
    passed = sum(t)
    results["passed"] += passed
    results["failed"] += len(t) - passed

    # ── TEST 2: Conflict Detection ────────────────────────────────
    separator("TEST 2 — Cross-Meeting Conflict Detection")
    print("  Running Meeting 2 pipeline (contains database conflict)...")
    result2 = analyze_meeting(MOCK_TRANSCRIPT_2)

    new_decisions = result2.get("decisions", [])
    past_decisions = [
        {"decision": d, "meeting_id": "meeting-1", "filename": "sprint_planning.mp3", "created_at": "2026-05-22"}
        for d in result1.get("decisions", [])
    ]

    print(f"\n  New decisions from Meeting 2: {len(new_decisions)}")
    print(f"  Past decisions from Meeting 1: {len(past_decisions)}")
    print("\n  Running conflict detection...")
    conflicts = detect_conflicts(new_decisions, past_decisions)

    print(f"\n  ⚠️ CONFLICTS FOUND: {len(conflicts)}")
    for c in conflicts:
        print(f"\n    🔴 NEW:  {c.get('new_decision')}")
        print(f"    🟡 PAST: {c.get('past_decision')}")
        print(f"    💬 WHY:  {c.get('explanation')}")

    separator("TEST 2 — Assertions")
    t2 = [
        check("Meeting 2 decisions extracted", result2.get("decisions")),
        check("Conflicts detected (DB conflict)", conflicts),
    ]
    passed2 = sum(t2)
    results["passed"] += passed2
    results["failed"] += len(t2) - passed2

    # ── TEST 3: RAG Search ────────────────────────────────────────
    separator("TEST 3 — Semantic RAG Search")
    meetings_data = [
        {"id": "m1", "filename": "sprint_planning.mp3", "transcript": MOCK_TRANSCRIPT_1, "created_at": "2026-05-22"},
        {"id": "m2", "filename": "followup_sync.mp3",   "transcript": MOCK_TRANSCRIPT_2, "created_at": "2026-05-29"},
    ]

    query = "What did we decide about the database?"
    print(f"  Query: \"{query}\"")
    rag_result = semantic_search_meetings(query, meetings_data)
    print(f"\n  🤖 Answer: {rag_result.get('answer', '')[:300]}")
    print(f"\n  📄 Sources: {len(rag_result.get('sources', []))} found")

    separator("TEST 3 — Assertions")
    t3 = [
        check("RAG answer generated", rag_result.get("answer")),
        check("Sources returned", rag_result.get("sources")),
    ]
    passed3 = sum(t3)
    results["passed"] += passed3
    results["failed"] += len(t3) - passed3

    # ── FINAL RESULTS ─────────────────────────────────────────────
    separator("FINAL TEST RESULTS")
    total = results["passed"] + results["failed"]
    print(f"\n  ✅ Passed : {results['passed']}/{total}")
    print(f"  ❌ Failed : {results['failed']}/{total}")
    score = (results["passed"] / total * 100) if total else 0
    print(f"\n  🏆 Score  : {score:.0f}%")

    if results["failed"] == 0:
        print("\n  🎉 ALL TESTS PASSED — Pipeline is working perfectly!")
    else:
        print("\n  ⚠️  Some tests failed — check output above.")

    return results["failed"] == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
