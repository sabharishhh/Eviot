from __future__ import annotations

import hashlib
import os
import torch
from typing import List, Optional

try:
    from backend.session import SentenceRecord
except ModuleNotFoundError:
    from session import SentenceRecord

try:
    from backend.memory.loader import load_okf_memories
except ModuleNotFoundError:
    from memory.loader import load_okf_memories


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Hard cap on how many memories can enter a single turn's pool. Without it,
# every memory ever written competes on every query, and the max-over-pool
# score drifts upward as the store grows — junk queries get more chances to
# clear the floor purely because there are more candidates.
MEMORY_TOP_K = _env_int("EVIOT_MEMORY_TOP_K", 8)

# Keyed by content hash, so an edited or superseded memory simply misses the
# cache rather than needing explicit invalidation.
_EMBED_CACHE: dict[str, torch.Tensor] = {}
_CACHE_MAX = _env_int("EVIOT_MEMORY_CACHE_MAX", 2000)


def _memory_texts(mem: dict) -> tuple[str, str]:
    """Split what gets embedded from what gets shown.

    The [MEMORY: ...] tag and markdown headers carry no semantic content but
    measurably dilute the vector — stripping them roughly halved similarity
    scores on unrelated queries during calibration. The tag stays on the
    display text because answer.py's trust hierarchy keys off that prefix.
    """
    meta = mem["metadata"]

    body_lines = [
        ln.strip() for ln in mem["body"].splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    clean_body = " ".join(body_lines)

    subject = meta.get("subject", "System")
    predicate = meta.get("predicate", "stated")
    obj = meta.get("object", "")
    mem_type = meta.get("type", "fact").upper()

    embed_text = f"{subject} {predicate} {obj}. {clean_body}".strip()
    display_text = f"[MEMORY: {mem_type}] {embed_text}"
    return embed_text, display_text


def _embeddings_for(texts: List[str], encoder) -> List[torch.Tensor]:
    """Embed with a content-addressed cache, batching any misses."""
    keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]

    missing_idx = [i for i, k in enumerate(keys) if k not in _EMBED_CACHE]
    if missing_idx:
        fresh = encoder.encode([texts[i] for i in missing_idx])
        for i, emb in zip(missing_idx, fresh):
            if len(_EMBED_CACHE) >= _CACHE_MAX:
                _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
            _EMBED_CACHE[keys[i]] = emb.cpu()

    return [_EMBED_CACHE[k] for k in keys]


def get_relevant_memory_records(
    query_embs: torch.Tensor,
    encoder,
    floor: Optional[float] = None,
) -> tuple[List["SentenceRecord"], dict]:
    """Score the on-demand memory store against this query and return only what
    clears the floor, capped at MEMORY_TOP_K and ordered by relevance.

    Standing memories (scope: always) are excluded here — they reach the prompt
    via get_standing_memories() instead. Scoring an instruction against the
    query guarantees it surfaces only when the user asks about it, which is
    exactly when it is least needed.

    Memories are deliberately NOT added to session.sentences — they are
    rebuilt per query. Injecting them into the persistent pool meant deleted
    and superseded memories lingered, every session file carried a duplicate
    snapshot, and irrelevant facts competed in every retrieval.
    """
    empty = {"total": 0, "kept": 0, "max_score": 0.0, "cache_size": len(_EMBED_CACHE)}

    if encoder is None:
        return [], empty

    memories = [m for m in load_okf_memories() if _scope_of(m) == "on_demand"]
    if not memories:
        return [], empty

    if floor is None:
        try:
            from retrieval.relevance import MEMORY_FLOOR
        except ModuleNotFoundError:
            from backend.retrieval.relevance import MEMORY_FLOOR
        floor = MEMORY_FLOOR

    pairs = [_memory_texts(m) for m in memories]
    embeddings = _embeddings_for([p[0] for p in pairs], encoder)

    q = query_embs.detach().cpu().float()
    if q.ndim == 1:
        q = q.unsqueeze(0)
    q = torch.nn.functional.normalize(q, dim=-1)

    M = torch.stack([e.detach().cpu().float().reshape(-1) for e in embeddings])
    M = torch.nn.functional.normalize(M, dim=-1)

    scores = (M @ q.T).max(dim=1).values

    ranked = sorted(
        range(len(memories)), key=lambda i: float(scores[i]), reverse=True
    )

    records = []
    for i in ranked:
        if float(scores[i]) < floor:
            break
        if len(records) >= MEMORY_TOP_K:
            break

        mem = memories[i]
        records.append(
            SentenceRecord(
                id=f"mem_{mem['metadata'].get('id')}",
                text=pairs[i][1],
                source_doc=f"Memory Store ({mem['file_name']})",
                source_line=1,
                embedding=embeddings[i],
            )
        )

    stats = {
        "total": len(memories),
        "kept": len(records),
        "max_score": round(float(scores.max()), 4),
        "cache_size": len(_EMBED_CACHE),
    }
    return records, stats

STANDING_MAX = _env_int("EVIOT_STANDING_MAX", 15)


def _scope_of(mem: dict) -> str:
    """Scope, inferred for memories written before the field existed."""
    scope = str(mem["metadata"].get("scope", "")).strip().lower()
    if scope in ("always", "on_demand"):
        return scope
    mem_type = str(mem["metadata"].get("type", "")).lower()
    return "always" if mem_type in ("preference", "decision") else "on_demand"


def get_standing_memories() -> List[str]:
    """Memories that apply regardless of the question.

    These bypass the relevance gate entirely — an instruction is not evidence,
    and scoring it against the query guarantees it only appears when the user
    asks about it, which is exactly when it is least needed.
    """
    out = []
    for mem in load_okf_memories():
        if _scope_of(mem) != "always":
            continue
        meta = mem["metadata"]
        body_lines = [ln.strip() for ln in mem["body"].splitlines()
                      if ln.strip() and not ln.strip().startswith("#")]
        out.append(" ".join(body_lines) or
                   f"{meta.get('subject')} {meta.get('predicate')} {meta.get('object')}")
        if len(out) >= STANDING_MAX:
            break
    return out