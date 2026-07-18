"""Tune EVIOT_HISTORY_FLOOR against LOCOMO.

Positives: a question scored against its OWN conversation (answer exists).
Negatives: the same question against a DIFFERENT conversation (no answer).
Same questions on both sides, so separation reflects answerability alone.

Run from repo root:  python probe_locomo.py
"""
import json
import random
import sys
import statistics as stats

sys.path.insert(0, "backend")

import torch
from dotenv import load_dotenv
load_dotenv()

from backend.eviot.encoders.encoder import Encoder

DATA = "/Users/sabharishhh/Developer/makesense/dataset/locomo10.json"
N_CONVERSATIONS = 4      # keep small; scores stabilise quickly
QUESTIONS_PER_CONV = 50
random.seed(0)


def conversation_turns(sample):
    """Flatten sessions into (dia_id, text) preserving speaker attribution."""
    conv = sample["conversation"]
    out = []
    for key in sorted(k for k in conv if k.startswith("session_") and isinstance(conv[k], list)):
        for turn in conv[key]:
            text = turn.get("text", "").strip()
            if text:
                out.append((turn.get("dia_id"),
                            f"[2026-07-18 15:44] {turn.get('speaker')} said: {text}"))
    return out


def norm(t):
    return torch.nn.functional.normalize(t.float(), dim=-1)


def main():
    data = json.load(open(DATA))[:N_CONVERSATIONS]
    encoder = Encoder()

    convs = []
    for sample in data:
        turns = conversation_turns(sample)
        print(f"  embedding {len(turns)} turns for {sample['sample_id']}...")

        # Batch to stay well inside per-request input limits.
        embs = []
        texts = [t[1] for t in turns]
        for i in range(0, len(texts), 256):
            embs.append(encoder.encode(texts[i:i + 256]))
        matrix = norm(torch.cat(embs))

        # Category 5 is adversarial-unanswerable-by-design; its evidence still
        # points into the conversation, so it belongs in neither class here.
        qa = [q for q in sample["qa"]
              if str(q.get("category")) != "5" and q.get("question")]
        qa = random.sample(qa, min(QUESTIONS_PER_CONV, len(qa)))

        convs.append({"id": sample["sample_id"], "matrix": matrix, "qa": qa})

    print("\n  embedding questions...")
    for c in convs:
        c["q_embs"] = norm(encoder.encode([q["question"] for q in c["qa"]]))

    positives, negatives = [], []
    for i, c in enumerate(convs):
        other = convs[(i + 1) % len(convs)]
        for row in range(len(c["qa"])):
            v = c["q_embs"][row:row + 1]
            positives.append(float((c["matrix"] @ v.T).max()))
            negatives.append(float((other["matrix"] @ v.T).max()))

    def describe(label, xs):
        xs = sorted(xs)
        print(f"  {label:10s} n={len(xs):4d}  "
              f"min={xs[0]:.3f}  p05={xs[int(.05 * len(xs))]:.3f}  "
              f"median={stats.median(xs):.3f}  "
              f"p95={xs[int(.95 * len(xs))]:.3f}  max={xs[-1]:.3f}")

    print()
    describe("answerable", positives)
    describe("unrelated", negatives)

    # Optimise for accuracy across the candidate range.
    best = max(
        ((sum(p >= t for p in positives) + sum(n < t for n in negatives)) /
         (len(positives) + len(negatives)), t)
        for t in [x / 100 for x in range(5, 80)]
    )
    acc, floor = best
    tpr = sum(p >= floor for p in positives) / len(positives)
    fpr = sum(n >= floor for n in negatives) / len(negatives)

    print(f"\n  best floor {floor:.2f} -> accuracy {acc:.1%} "
          f"(opens on {tpr:.1%} of answerable, {fpr:.1%} of unrelated)")
    print(f"\n  EVIOT_HISTORY_FLOOR={floor:.2f}")


if __name__ == "__main__":
    main()