"""Tune EVIOT_RELEVANCE_FLOOR against the demo documents.

Positives: a question scored against the doc that answers it.
Negatives: the same question against the OTHER doc.
Same questions on both sides, so separation reflects answerability alone.

Chunks via the real ingestion chunker — document "sentences" in the pool are
paragraph-sized chunks (40-250 words), not single sentences, and length
strongly affects similarity.

Run from repo root:  python probe_docs.py
"""
import sys
import statistics as stats

sys.path.insert(0, "backend")

import torch
from dotenv import load_dotenv
load_dotenv()

from backend.eviot.encoders.encoder import Encoder
from backend.ingestion.chunker import chunk_into_sentences

DOCS = {
    "bitcoin": "backend/demo/data/bitcoin/consensus.txt",
    "insulin": "backend/demo/data/medical/insulin.txt",
}

QUESTIONS = {
    "bitcoin": [
        "Who published the Bitcoin white paper?",
        "What problem did the white paper solve?",
        "When was the genesis block created?",
        "What was hardcoded into the genesis block?",
        "How does the network replace trust in intermediaries?",
        "What happened to Nakamoto after 2010?",
        "How does proof-of-work reach consensus?",
        "What is the maximum supply of coins?",
        "What environmental criticism has mining attracted?",
        "Why does removing clearing houses matter?",
    ],
    "insulin": [
        "Who isolated the pancreatic hormone?",
        "Where and when was insulin discovered?",
        "Who was the first human patient treated?",
        "Who received the Nobel Prize for the discovery?",
        "What causes Type 1 diabetes?",
        "What killed pediatric diabetes patients before 1921?",
        "How did manufacturing change with recombinant DNA?",
        "What are the risks of incorrect dosage?",
        "What is diabetic ketoacidosis?",
        "How does insulin affect glucose transport?",
    ],
}


def norm(t):
    return torch.nn.functional.normalize(t.detach().cpu().float(), dim=-1)


def main():
    encoder = Encoder()

    pools = {}
    for name, path in DOCS.items():
        text = open(path, encoding="utf-8").read()
        chunks = chunk_into_sentences(text, encoder)
        pools[name] = norm(encoder.encode(chunks))
        words = [len(c.split()) for c in chunks]
        print(f"  {name}: {len(chunks)} chunks, {min(words)}-{max(words)} words each")

    print()
    positives, negatives = [], []

    for name, qs in QUESTIONS.items():
        other = next(k for k in pools if k != name)
        q_embs = norm(encoder.encode(qs))

        print(f"=== {name} ===")
        print(f"  {'own':>6}  {'other':>6}   question")
        for i, q in enumerate(qs):
            v = q_embs[i:i + 1]
            own = float((pools[name] @ v.T).max())
            oth = float((pools[other] @ v.T).max())
            positives.append(own)
            negatives.append(oth)
            print(f"  {own:6.4f}  {oth:6.4f}   {q}")
        print()

    def describe(label, xs):
        xs = sorted(xs)
        print(f"  {label:10s} n={len(xs):3d}  min={xs[0]:.4f}  "
              f"p05={xs[int(.05 * len(xs))]:.4f}  median={stats.median(xs):.4f}  "
              f"p95={xs[int(.95 * len(xs))]:.4f}  max={xs[-1]:.4f}")

    describe("answerable", positives)
    describe("unrelated", negatives)

    junk_max = max(negatives)
    real_min = min(positives)

    if real_min > junk_max:
        print(f"\n  separated -> EVIOT_RELEVANCE_FLOOR={(junk_max + real_min) / 2:.2f}")
    else:
        best = max(
            ((sum(p >= t for p in positives) + sum(n < t for n in negatives)) /
             (len(positives) + len(negatives)), t)
            for t in [x / 100 for x in range(5, 90)]
        )
        acc, floor = best
        print(f"\n  overlap (junk_max={junk_max:.4f} real_min={real_min:.4f})")
        print(f"  best accuracy {acc:.1%} at EVIOT_RELEVANCE_FLOOR={floor:.2f}")


if __name__ == "__main__":
    main()