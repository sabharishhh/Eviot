"""Measure real relevance scores against the live memory store.

Run from repo root:  python probe_gate.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import torch
from dotenv import load_dotenv
load_dotenv()

from eviot.encoders.encoder import Encoder
from memory.loader import load_okf_memories

SHOULD_CLOSE = [
    "hii", "thanks", "write me a haiku", "what's 12 * 7",
    "explain recursion", "what did we decide about encryption",
]
SHOULD_OPEN = ["what is my name", "who am i", "what should i be called"]


def main():
    encoder = Encoder()
    memories = load_okf_memories()

    if not memories:
        print("No active memories found. Run from repo root so .eviot/ resolves.")
        return

    # Rebuild dense_text exactly as sync_memory_to_session does.
    texts, labels = [], []
    for mem in memories:
        meta = mem["metadata"]
        body_lines = [
            ln.strip() for ln in mem["body"].splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        texts.append(
            f"{meta.get('subject')} {meta.get('predicate')} "
            f"{meta.get('object', '')}. {' '.join(body_lines)}".strip()
        )
        labels.append(f"{meta.get('subject')} {meta.get('predicate')} {meta.get('object')}")

    M = torch.nn.functional.normalize(encoder.encode(texts).float(), dim=-1)

    def probe(group, queries):
        print(f"\n=== {group} ===")
        peak = 0.0
        for q in queries:
            v = torch.nn.functional.normalize(encoder.encode(q).float(), dim=-1)
            sims = (M @ v.T).max(dim=1).values
            top = int(sims.argmax())
            score = float(sims[top])
            peak = max(peak, score) if group == "SHOULD CLOSE" else peak
            print(f"  {score:.4f}  {q!r}  ->  {labels[top]}")
        return peak

    print(f"Scoring {len(memories)} active memories with {encoder.model_name}")
    close_peak = probe("SHOULD CLOSE", SHOULD_CLOSE)
    probe("SHOULD OPEN", SHOULD_OPEN)

    open_scores = []
    for q in SHOULD_OPEN:
        v = torch.nn.functional.normalize(encoder.encode(q).float(), dim=-1)
        open_scores.append(float((M @ v.T).max()))
    open_min = min(open_scores)

    print(f"\nhighest junk score : {close_peak:.4f}")
    print(f"lowest real score  : {open_min:.4f}")
    if open_min > close_peak:
        print(f"separated -> set EVIOT_MEMORY_FLOOR={(close_peak + open_min) / 2:.2f}")
    else:
        print("OVERLAP -> no threshold works; the score needs rework")

if __name__ == "__main__":
    main()