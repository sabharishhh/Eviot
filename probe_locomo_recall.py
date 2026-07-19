"""Evidence-recall benchmark against LOCOMO.

For each question we ask the engine to retrieve, and score the retrieved
sentence IDs against the annotated evidence turns. No answer generation, no
extraction, no summary — only the engine's context-assembly.

Costs an embedding call per turn plus a resolver/expansion-free /query per
question. Approximately: 1 conversation ≈ 500 turns + 200 questions.

Run from repo root:  python probe_locomo_recall.py [n_conversations] [n_questions]
"""
import json
import random
import sys
import time
from collections import defaultdict, Counter

import requests
import torch
from dotenv import load_dotenv
load_dotenv()

from backend.eviot.encoders.encoder import Encoder

ENGINE = "naive"
BASE = "http://localhost:8000"
DATA = "./dataset/locomo10.json"
N_CONV = int(sys.argv[1]) if len(sys.argv) > 1 else 1
N_QS = int(sys.argv[2]) if len(sys.argv) > 2 else 40
random.seed(0)


def sentence_records_from(sample, encoder):
    """Build LocomoSentenceIn payload: dia_id becomes the sentence id, so
    the retrieval events come back labelled with the same IDs LOCOMO annotated.
    """
    conv = sample["conversation"]
    turns = []
    for key in sorted(k for k in conv if k.startswith("session_") and isinstance(conv[k], list)):
        for t in conv[key]:
            text = (t.get("text") or "").strip()
            if text:
                turns.append((t["dia_id"], f"{t.get('speaker')}: {text}"))

    print(f"  embedding {len(turns)} turns...")
    embs = []
    for i in range(0, len(turns), 256):
        embs.append(encoder.encode([t[1] for t in turns[i:i + 256]]))
    matrix = torch.cat(embs)

    return [{
        "id": tid,
        "text": text,
        "source_doc": "conversation",
        "source_line": 1,
        "embedding": matrix[i].tolist(),
    } for i, (tid, text) in enumerate(turns)]


def load_session(records):
    r = requests.post(f"{BASE}/eval/locomo/load", json={"sentences": records}, timeout=180)
    r.raise_for_status()
    return r.json()["session_id"]


def retrieve(sid, question):
    """Runs /query with is_eval=True — LLM path skipped, just parse sources."""
    payload = {
        "session_id": sid, "query": question, "mode": "adaptive",
        "use_decomposition": True, "retrieval_engine": ENGINE,
        "params": {"epsilon": 0.01, "patience": 2, "k_max": 12, "k": 5},
        "is_eval": True,
    }
    retrieved = []
    gate = None
    with requests.post(f"{BASE}/query", json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue
            try:
                ev = json.loads(raw[6:])
            except json.JSONDecodeError:
                continue
            k = ev.get("type") or ev.get("event")
            if k == "selection_step":
                retrieved.append(ev.get("sentence_id"))
            elif k == "relevance_gate":
                gate = ev
    return retrieved, gate


def score(retrieved, evidence, pool):
    ret, ev = set(retrieved), set(evidence)
    reachable = ev & pool
    if not reachable:
        return None
    hit = len(ret & reachable)
    return {
        "recall": hit / len(reachable),
        "precision": hit / len(ret) if ret else 0.0,
        "retrieved": len(ret),
        "expected": len(reachable),
        "unreachable": len(ev - pool),
    }


def main():
    try:
        requests.get(f"{BASE}/sessions", timeout=5).raise_for_status()
    except Exception as e:
        print(f"Backend not reachable at {BASE} — start uvicorn first.\n  {e}")
        sys.exit(1)

    data = json.load(open(DATA))[:N_CONV]
    encoder = Encoder()

    per_cat = defaultdict(list)
    rows = []
    gated_out = 0

    for sample in data:
        print(f"\n=== {sample['sample_id']} ===")
        records = sentence_records_from(sample, encoder)
        pool = {r["id"] for r in records}
        sid = load_session(records)
        print(f"  session {sid}, {len(records)} turns loaded")

        qa = [q for q in sample["qa"]
              if str(q.get("category")) != "5" and q.get("evidence")]
        qa = random.sample(qa, min(N_QS, len(qa)))

        for i, q in enumerate(qa, 1):
            retrieved, gate = retrieve(sid, q["question"])
            m = score(retrieved, q["evidence"], pool)
            if m is None:
                continue

            # A closed gate means nothing was retrieved at all. That is a
            # threshold decision, not the engine failing to find evidence —
            # counting it as recall 0.0 would blame the wrong component.
            m["gate_passed"] = bool(gate and gate.get("passed"))
            m["gate_reason"] = gate.get("reason") if gate else "no_gate_event"
            m["max_relevance"] = gate.get("max_relevance") if gate else None
            if not m["gate_passed"]:
                gated_out += 1

            m["category"] = q["category"]
            m["question"] = q["question"]
            m["evidence"] = q["evidence"]
            m["retrieved_ids"] = retrieved
            per_cat[q["category"]].append(m)
            rows.append(m)

            if i % 10 == 0:
                print(f"    {i}/{len(qa)}...")

    out = f"locomo_recall_{ENGINE}_{N_CONV}x{N_QS}.json"
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"\n  raw rows -> {out}")

    def report(title, subset):
        print("\n" + "=" * 66)
        print(f"{title}")
        print(f"{'category':>10}  {'n':>4}  {'recall':>7}  {'precision':>10}  {'ret':>5}  {'exp':>5}")
        print("=" * 66)
        by_cat = defaultdict(list)
        for r in subset:
            by_cat[r["category"]].append(r)
        for cat in sorted(by_cat):
            rs = by_cat[cat]
            print(f"{cat:>10}  {len(rs):>4}  "
                  f"{sum(r['recall'] for r in rs)/len(rs):>7.1%}  "
                  f"{sum(r['precision'] for r in rs)/len(rs):>10.1%}  "
                  f"{sum(r['retrieved'] for r in rs)/len(rs):>5.1f}  "
                  f"{sum(r['expected'] for r in rs)/len(rs):>5.1f}")
        if subset:
            print("=" * 66)
            print(f"{'overall':>10}  {len(subset):>4}  "
                  f"{sum(r['recall'] for r in subset)/len(subset):>7.1%}  "
                  f"{sum(r['precision'] for r in subset)/len(subset):>10.1%}")

    report(f"ALL QUESTIONS  (engine={ENGINE})", rows)

    passed = [r for r in rows if r["gate_passed"]]
    if gated_out:
        report(f"GATE-PASSED ONLY  ({gated_out}/{len(rows)} gated out)", passed)
        reasons = Counter(r["gate_reason"] for r in rows if not r["gate_passed"])
        print(f"\n  gate rejections: {dict(reasons)}")

    orphans = sum(r["unreachable"] for r in rows)
    if orphans:
        print(f"  evidence refs not in pool: {orphans} (excluded from scoring)")

if __name__ == "__main__":
    main()