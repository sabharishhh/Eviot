"""Measure real relevance scores against the live memory store.

Run from repo root:  python probe_gate.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import torch
from dotenv import load_dotenv
load_dotenv()

from backend.eviot.encoders.encoder import Encoder
from backend.memory.loader import load_okf_memories

SHOULD_CLOSE = [
    "hii", "thanks", "write me a haiku", "what's 12 * 7",
    "explain recursion", "what did we decide about encryption",
]
SHOULD_OPEN = ["what is my name", "who am i", "what should i be called"]

BACKGROUND = [
    "The train arrives at the station shortly after noon.",
    "Photosynthesis converts light energy into chemical energy.",
    "She adjusted the carburettor before the race.",
    "Quarterly earnings exceeded analyst expectations.",
    "The recipe calls for two cups of flour.",
    "Tectonic plates shift a few centimetres each year.",
    "He renewed his passport at the consulate.",
    "The algorithm runs in logarithmic time.",
    "Rainfall was heavier than average last season.",
    "The museum closes at six on weekdays.",
    "Copper conducts electricity better than iron.",
    "They repainted the fence a darker shade of green.",
    "The contract expires at the end of the quarter.",
    "Bees pollinate a third of the food supply.",
    "The bridge was completed ahead of schedule.",
    "Sourdough needs a longer proving time.",
    "Interest rates held steady this month.",
    "The novel was translated into twelve languages.",
    "Volcanic ash disrupted flights across the region.",
    "He tuned the guitar before the set.",
]

def main():
    encoder = Encoder()
    memories = load_okf_memories()

    if not memories:
        print("No active memories found. Run from repo root so .eviot/ resolves.")
        return

    texts, labels = [], []
    for mem in memories:
        meta = mem["metadata"]
        body_lines = [ln.strip() for ln in mem["body"].splitlines()
                      if ln.strip() and not ln.strip().startswith("#")]
        texts.append(f"{meta.get('subject')} {meta.get('predicate')} "
                     f"{meta.get('object', '')}. {' '.join(body_lines)}".strip())
        labels.append(f"{meta.get('subject')} {meta.get('predicate')} {meta.get('object')}")

    M = torch.nn.functional.normalize(encoder.encode(texts).float(), dim=-1)
    B = torch.nn.functional.normalize(encoder.encode(BACKGROUND).float(), dim=-1)

    print(f"Scoring {len(memories)} memories against {len(BACKGROUND)} background sentences\n")
    print(f"  {'raw':>6}  {'bg':>6}  {'margin':>7}   query")

    def probe(group, queries):
        print(f"\n=== {group} ===")
        out = []
        for q in queries:
            v = torch.nn.functional.normalize(encoder.encode(q).float(), dim=-1)
            raw = float((M @ v.T).max())
            bg = float((B @ v.T).max())
            out.append((raw, raw - bg))
            print(f"  {raw:6.4f}  {bg:6.4f}  {raw - bg:+7.4f}   {q!r}")
        return out

    close = probe("SHOULD CLOSE", SHOULD_CLOSE)
    open_ = probe("SHOULD OPEN", SHOULD_OPEN)

    for i, name in ((0, "raw score"), (1, "margin")):
        cj = max(c[i] for c in close)
        lo = min(o[i] for o in open_)
        verdict = (f"separated -> threshold {(cj + lo) / 2:.3f}"
                   if lo > cj else "OVERLAP")
        print(f"\n  {name:10s} junk_max={cj:+.4f}  real_min={lo:+.4f}  {verdict}")

if __name__ == "__main__":
    main()