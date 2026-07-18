"""End-to-end tests for the session / gate / memory / summary pipeline.

Backend must be running:  uvicorn backend.main:app
Then, from repo root:     python test_flow.py

NOTE: these are live calls. Background memory extraction runs on every turn,
so this WILL write to .eviot/memory. Check activity_log.txt afterwards and
prune anything unwanted — in particular, test 3 writes a Lisbon trip memory
that will inflate turn-1 scores on the next run if left in place.

Test 1 assumes a memory recording the user's name already exists in the store.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path
import os

import requests

from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8000"
DB_PATH = Path(".eviot/sessions.db")

PASS, FAIL = "PASS", "FAIL"
results = []


def record(name, ok, detail=""):
    results.append((name, PASS if ok else FAIL, detail))
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name}" + (f"  — {detail}" if detail else ""))


def new_session():
    r = requests.post(f"{BASE}/session", timeout=30)
    r.raise_for_status()
    return r.json()["session_id"]


def ask(session_id, query):
    """Run one query, return {gate, sources, answer}."""
    payload = {
        "session_id": session_id,
        "query": query,
        "mode": "adaptive",
        "use_decomposition": True,
        "retrieval_engine": "ot",
        "params": {"epsilon": 0.01, "patience": 2, "k_max": 12, "k": 5},
    }
    gate, sources, answer = None, [], ""

    with requests.post(f"{BASE}/query", json=payload, stream=True, timeout=180) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue
            try:
                ev = json.loads(raw[6:])
            except json.JSONDecodeError:
                continue

            kind = ev.get("type") or ev.get("event")
            if kind == "relevance_gate":
                gate = ev
            elif kind == "selection_step":
                sources.append(ev.get("source_doc", ""))
            elif kind == "llm_token":
                answer += ev.get("token", "")
            elif kind == "stream_error":
                raise RuntimeError(f"stream_error: {ev.get('detail')}")

    if gate is None:
        raise RuntimeError("no relevance_gate event — is the SSE field added?")
    return {"gate": gate, "sources": sources, "answer": answer}


def db_summary(session_id):
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT summary, summary_through_turn FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row if row else None
    finally:
        conn.close()


# ─── Test 1: self-match ──────────────────────────────────────────────────────

def test_self_match():
    print("\n[1] Self-match — same question twice must not match itself")
    sid = new_session()

    a = ask(sid, "what is my name")
    b = ask(sid, "what is my name")

    ra, rb = a["gate"]["max_relevance"], b["gate"]["max_relevance"]
    resolved = b["gate"].get("resolved_query")

    print(f"      turn1 max_rel={ra}  turn2 max_rel={rb}")
    print(f"      turn2 resolved={resolved!r}")

    record("score stays flat", rb <= ra + 0.02, f"{ra} -> {rb}")
    record("turn records hidden", b["gate"].get("hidden_records", 0) >= 2,
           f"hidden={b['gate'].get('hidden_records')}")
    record("no conversation_history retrieved",
           not any("conversation" in s for s in b["sources"]),
           f"sources={b['sources']}")

    # resolve_query_with_history can substitute an answer from history back into
    # the question ("what is my name" -> "What is <name>'s name?"), making the
    # query contain its own answer. Harmless for retrieval, fatal for the gate.
    # Non-deterministic, so treat a pass as a canary rather than proof.
    if not resolved:
        record("resolver did not inject the answer into the query", False,
               "resolved_query missing from SSE event — check cannot run")
    else:
        leaked = "sabharish" in resolved.lower()
        record("resolver did not inject the answer into the query",
               not leaked, resolved if leaked else "")


# ─── Test 2: repetition loophole ─────────────────────────────────────────────

def test_repetition_loophole():
    print("\n[2] Repetition — saying junk twice must not open the gate")
    sid = new_session()

    a = ask(sid, "hii")
    b = ask(sid, "hii")

    print(f"      turn1 passed={a['gate']['passed']}  turn2 passed={b['gate']['passed']}"
          f"  max_rel={b['gate']['max_relevance']}")

    record("first stays closed", not a["gate"]["passed"], a["gate"]["reason"])
    record("second stays closed", not b["gate"]["passed"], b["gate"]["reason"])
    record("no sources shown", len(b["sources"]) == 0, f"sources={b['sources']}")


# ─── Test 3 + 4: archiving, summary, old-turn recall ─────────────────────────

TOPIC_TURNS = [
    "I am planning a trip to Lisbon in October",
    "What neighbourhood should I stay in there",
    "How many days is enough for the city",
    "Is it worth taking a day trip to Sintra",
    "What is the weather usually like that month",
    "Should I rent a car or use public transport",
    "What food should I try while I am there",
    "Any tips for avoiding tourist crowds",
    "Is tipping expected in restaurants",
]


def test_archiving_and_recall():
    print("\n[3] Archiving + summary — 9 turns, expect window to cap and summary to appear")
    sid = new_session()

    gates = []
    for i, q in enumerate(TOPIC_TURNS, start=1):
        g = ask(sid, q)["gate"]
        gates.append(g)
        print(f"      turn{i}: visible={g.get('turns_visible')} "
              f"pool={g['pool_size']} summary={'y' if g.get('has_summary') else 'n'}")

    visibles = [g.get("turns_visible", 0) for g in gates]
    record("visible window caps at 6", max(visibles) <= 6, f"max visible={max(visibles)}")
    record("pool grows as turns archive",
           gates[-1]["pool_size"] > gates[2]["pool_size"],
           f"{gates[2]['pool_size']} -> {gates[-1]['pool_size']}")

    # Turns 1-6 legitimately have an empty pool in a doc-less session: every turn
    # is still inside the visible window, so nothing is archived and nothing is
    # retrievable. Only from turn 7 onward should the pool be populated.
    record("pool grows once archiving starts",
           all(g["pool_size"] > 0 for g in gates[6:]),
           f"pool sizes: {[g['pool_size'] for g in gates]}")

    # Summary is written by a background task. Wait for it to settle rather than
    # grabbing the first one written — turn 8's task and turn 9's can both be in
    # flight, and the first to land is not the final state.
    print("      waiting for background summary...")
    summary, through, stable = None, 0, 0
    for _ in range(20):
        time.sleep(2)
        row = db_summary(sid)
        if row and row[0]:
            if row[0] == summary:
                stable += 1
                if stable >= 2:
                    break
            else:
                stable = 0
            summary, through = row[0], row[1]

    record("summary was written", bool(summary),
           f"through_turn={through}" if summary else "none after 40s")

    if summary:
        print(f"\n      --- summary ---\n      {summary}\n")
        record("summary is not trivially short", len(summary.split()) >= 15,
               f"{len(summary.split())} words")

        restates = "sabharish" in summary.lower()
        record("summary does not just restate memories",
               not restates,
               "contains user name — prompt may need tightening" if restates else "")

    print("\n[4] Old-turn recall — ask about turn 1, now archived")
    r = ask(sid, "which city did I say I was travelling to")
    print(f"      max_rel={r['gate']['max_relevance']} sources={r['sources']}")

    record("archived turn is retrievable",
           any("conversation" in s for s in r["sources"]),
           f"sources={r['sources']}")
    record("answer mentions Lisbon", "lisbon" in r["answer"].lower(),
           r["answer"][:80])

    # The check above can pass for the wrong reason. A memory clearing its own
    # (much lower) floor opens the gate, after which archived turns enter as
    # prefilter candidates via the relaxed margin — even when history alone
    # would never have qualified. Assert the gate would have opened regardless.
    #
    # Not airtight: max_relevance is the max across the whole pool, so a
    # high-scoring memory could satisfy it. Combined with the presence of
    # history sources it's a reasonable proxy; tightening it further would
    # need per-source scores in the relevance_gate event.
    history_floor = float(os.getenv("EVIOT_HISTORY_FLOOR", 0.32))
    hist_sources = [s for s in r["sources"] if "conversation" in s]
    record("history clears its own floor, not carried by memory",
           r["gate"]["max_relevance"] >= history_floor and len(hist_sources) > 0,
           f"max_rel={r['gate']['max_relevance']} floor={history_floor} "
           f"history_sources={len(hist_sources)}")

# ─── Runner ──────────────────────────────────────────────────────────────────

def main():
    try:
        requests.get(f"{BASE}/sessions", timeout=5).raise_for_status()
    except Exception as e:
        print(f"Backend not reachable at {BASE} — start uvicorn first.\n  {e}")
        sys.exit(1)

    print("Running live tests. This makes real LLM calls and takes a few minutes.")
    print("Background memory extraction will write to .eviot/memory.\n")

    test_self_match()
    test_repetition_loophole()
    test_archiving_and_recall()

    print("\n" + "=" * 60)
    failed = [r for r in results if r[1] == FAIL]
    for name, status, detail in results:
        print(f"  {status}  {name}" + (f"  ({detail})" if detail else ""))
    print("=" * 60)
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()