"""Realistic end-to-end session — read the transcript, don't just count passes.

Exercises what the unit tests don't: documents present, grounded and open mode
interleaved in one session, memory declared then recalled across sessions.

Backend must be running.  Run from repo root:  python usage_run.py
"""
import sys
import time

import requests

from test_flow import BASE, ask, new_session

DOC = "backend/demo/data/bitcoin/consensus.txt"
notes = []


def ingest(path, session_id=None):
    with open(path, "rb") as fh:
        params = {"session_id": session_id} if session_id else {}
        r = requests.post(f"{BASE}/ingest", files={"files": (path.split("/")[-1], fh)},
                          params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def turn(sid, q, expect=None, why=""):
    """Run a turn and print it as a transcript entry."""
    r = ask(sid, q)
    g = r["gate"]
    mode = "GROUNDED" if r["sources"] else "open"

    print(f"\n  > {q}")
    if g.get("resolved_query") and g["resolved_query"].lower() != q.lower():
        print(f"    (resolved: {g['resolved_query']})")
    print(f"    [{mode}] score={g['max_relevance']:.3f} "
          f"pool={g['pool_size']} sources={len(r['sources'])}")
    if r["sources"]:
        for s in dict.fromkeys(r["sources"]):
            print(f"      · {s}")
    print(f"    {r['answer'][:280].strip()}")

    if expect and mode.lower() != expect.lower():
        notes.append(f"expected {expect} but got {mode}: {q!r} — {why}")
    return r


def main():
    try:
        requests.get(f"{BASE}/sessions", timeout=5).raise_for_status()
    except Exception as e:
        print(f"Backend not reachable at {BASE} — start uvicorn first.\n  {e}")
        sys.exit(1)

    print("=" * 70)
    print("PHASE 1 — general chat, nothing ingested")
    print("=" * 70)
    sid = new_session()
    turn(sid, "hey, what can you help me with?", expect="open",
         why="no documents exist yet")
    turn(sid, "explain what a hash function does in one sentence", expect="open",
         why="general knowledge, nothing ingested")

    print("\n" + "=" * 70)
    print("PHASE 2 — declare a fact, expect it to reach long-term memory")
    print("=" * 70)
    turn(sid, "by the way, I prefer short answers without bullet points")
    print("\n  waiting for background extraction...")
    time.sleep(10)

    print("\n" + "=" * 70)
    print("PHASE 3 — ingest a document mid-conversation")
    print("=" * 70)
    info = ingest(DOC, sid)
    print(f"  ingested: {info.get('total_sentences')} chunks "
          f"into session {info.get('session_id')}")

    print("\n" + "=" * 70)
    print("PHASE 4 — document questions (should be GROUNDED)")
    print("=" * 70)
    turn(sid, "who published the bitcoin white paper?", expect="grounded",
         why="clearly answered by the ingested doc")
    # Scored 0.3471 offline — above 0.24 but the closest legitimate question
    # to the floor, so it is the one that reveals a mis-set threshold.
    turn(sid, "what problem did the white paper solve?", expect="grounded",
         why="borderline score offline (0.347); tests the floor in practice")
    turn(sid, "and when was the genesis block created?", expect="grounded",
         why="elliptical follow-up, tests resolver plus retrieval together")

    print("\n" + "=" * 70)
    print("PHASE 5 — general question WITH a document loaded")
    print("=" * 70)
    # The important one. A doc is in the pool; an unrelated question must not
    # drag it in and answer as though it were sourced.
    turn(sid, "what should I cook for dinner tonight?", expect="open",
         why="unrelated to the doc — must not falsely ground")
    turn(sid, "thanks, that helps", expect="open",
         why="social filler with a doc loaded")

    print("\n" + "=" * 70)
    print("PHASE 6 — back to the document")
    print("=" * 70)
    turn(sid, "what environmental criticism has mining attracted?", expect="grounded",
         why="doc content again after an open-mode detour")

    print("\n" + "=" * 70)
    print("PHASE 7 — push past the window so archiving and summary kick in")
    print("=" * 70)
    for q in ["how does proof-of-work reach consensus?",
              "what is the maximum supply?",
              "what happened to Nakamoto after 2010?"]:
        turn(sid, q)

    print("\n  waiting for background summary...")
    time.sleep(12)

    print("\n" + "=" * 70)
    print("PHASE 8 — NEW session: does the preference survive?")
    print("=" * 70)
    sid2 = new_session()
    turn(sid2, "how do you know I like my answers formatted?")
    turn(sid2, "what did we discuss about bitcoin?",
         why="different session — should NOT recall; docs are per-session")

    print("\n" + "=" * 70)
    if notes:
        print("MODE MISMATCHES")
        for n in notes:
            print(f"  · {n}")
    else:
        print("No mode mismatches.")
    print("\nRead the transcript above — answer quality, source relevance, and")
    print("whether open-mode replies sound natural are judgement calls, not asserts.")
    print("=" * 70)


if __name__ == "__main__":
    main()