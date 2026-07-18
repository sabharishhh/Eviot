from __future__ import annotations

import os
import torch
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # avoids a hard dependency on sys.path layout at import time
    from session import SentenceRecord


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Calibrate these against your encoder — they are the single most important
# knob in the general-chat flow. Too high: grounded questions fall through to
# open mode. Too low: memories leak into unrelated chat.
RELEVANCE_FLOOR = _env_float("EVIOT_RELEVANCE_FLOOR", 0.38)   # prose sentences
MEMORY_FLOOR = _env_float("EVIOT_MEMORY_FLOOR", 0.20)         # terse [MEMORY:] lines
HISTORY_FLOOR = _env_float("EVIOT_HISTORY_FLOOR", 0.40)       # past turns, noisiest
PREFILTER_MARGIN = _env_float("EVIOT_PREFILTER_MARGIN", 0.10)
PREFILTER_ENABLED = os.getenv("EVIOT_PREFILTER", "1") != "0"


def _is_memory(rec: SentenceRecord) -> bool:
    return rec.id.startswith("mem_")


def _is_history(rec: SentenceRecord) -> bool:
    return rec.source_doc == "conversation_history"


def _floor_for(rec: SentenceRecord) -> float:
    if _is_memory(rec):
        return MEMORY_FLOOR
    if _is_history(rec):
        return HISTORY_FLOOR
    return RELEVANCE_FLOOR


def score_records(q_embs: torch.Tensor, records: List[SentenceRecord]) -> torch.Tensor:
    """Max cosine similarity of each record against any query sub-embedding.

    Returns shape (n_records,). Normalizes explicitly so this is correct
    regardless of whether the encoder emits unit vectors.
    """
    if not records:
        return torch.empty(0)

    q = q_embs.detach().cpu().float()
    if q.ndim == 1:
        q = q.unsqueeze(0)
    q = torch.nn.functional.normalize(q, dim=-1)

    m = torch.stack([r.embedding.detach().cpu().float().reshape(-1) for r in records])
    m = torch.nn.functional.normalize(m, dim=-1)

    sims = m @ q.T                      # (n_records, n_phrases)
    return sims.max(dim=1).values       # (n_records,)


def filter_relevant_records(
    q_embs: torch.Tensor,
    records: List[SentenceRecord],
) -> Tuple[List[SentenceRecord], float]:
    """Absolute relevance gate in front of OT selection.

    build_context_set_adaptive() stops on *marginal* cost decay and always
    returns at least one sentence — it has no notion of "nothing here is
    relevant". This supplies that floor.

    Returns (candidate_records, max_score). An empty candidate list means the
    gate is closed and the turn should be answered in open mode.
    """
    if not records:
        return [], 0.0

    scores = score_records(q_embs, records)
    floors = torch.tensor([_floor_for(r) for r in records], dtype=scores.dtype)

    max_score = float(scores.max())

    # Gate: does anything clear its own floor?
    if not bool((scores >= floors).any()):
        return [], max_score

    if not PREFILTER_ENABLED:
        return list(records), max_score

    # Candidate pool: keep near-misses too. OT's value is combining sentences
    # that are individually weak but jointly cover the query, so pruning to
    # only floor-passing records would defeat multi-hop retrieval.
    relaxed = floors - PREFILTER_MARGIN
    keep = scores >= relaxed

    candidates = [rec for rec, k in zip(records, keep.tolist()) if k]
    return candidates, max_score