import torch
import re
from typing import Generator, List
from eviot.ot.cost import ot_cost
from session import SentenceRecord

# --- LINGUISTIC DECOMPOSITION CONSTANTS ---
_STOPWORDS = {
    "what", "how", "does", "do", "can", "is", "are",
    "the", "a", "an", "of", "in", "on", "for", "to", "with"
}

_INTERROGATIVES = {
    "what", "how", "does", "do", "can", "is", "are"
}

# --- HELPER FUNCTIONS ---
def _normalize(text: str) -> str:
    return text.lower().strip()

def _is_interrogative(text: str) -> bool:
    tokens = text.split()
    return bool(tokens and tokens[0].lower() in _INTERROGATIVES)

def _content_words(span):
    return [
        t.text.lower()
        for t in span
        if t.is_alpha and t.text.lower() not in _STOPWORDS
    ]

def _suppress_subphrases(phrases):
    final = []
    for p in phrases:
        drop = False
        for q in phrases:
            if p == q:
                continue
            if p in q and len(q.split()) > len(p.split()):
                drop = True
                break
        if not drop:
            final.append(p)
    return final

# --- ENCODING PIPELINE ---
def encode_query_plain(query: str, encoder) -> torch.Tensor:
    """Embed query as a single vector. Returns shape (1, 768)."""
    emb = encoder.encode(query)
    if emb.ndim == 1:
        emb = emb.unsqueeze(0)
    return emb.cpu()

def encode_query_decomposed(query: str, encoder) -> tuple[list[str], torch.Tensor]:
    """
    Advanced query decomposition using spaCy verb-spans and noun-chunks.
    Preserves verbs and distinct semantic targets essential for multi-hop OT retrieval.
    """
    from ingestion.chunker import get_nlp
    nlp = get_nlp()
    doc = nlp(query)
    
    query_tokens = {t.text.lower() for t in doc if t.is_alpha}
    candidates = []

    # 1. Extract Noun Chunks
    for chunk in doc.noun_chunks:
        if len(_content_words(chunk)) >= 2:
            candidates.append(chunk.text)

    # 2. Extract significant standalone nouns
    for token in doc:
        if token.pos_ in {"NOUN", "PROPN"} and token.text.lower() not in _STOPWORDS:
            candidates.append(token.text)

    # 3. Extract Verb Spans (Crucial for multi-hop actions)
    for token in doc:
        if token.pos_ == "VERB":
            span = doc[token.left_edge.i: token.right_edge.i + 1]
            if len(_content_words(span)) >= 2:
                candidates.append(span.text)

    # 4. Deduplicate
    seen = set()
    unique_candidates = []
    for c in candidates:
        norm_c = _normalize(c)
        if norm_c not in seen:
            seen.add(norm_c)
            unique_candidates.append(norm_c)

    # 5. Filter out interrogatives and oversized chunks
    filtered = []
    for c in unique_candidates:
        if _is_interrogative(c):
            continue
        overlap = len(set(c.split()) & query_tokens) / max(len(query_tokens), 1)
        if overlap < 0.7:
            filtered.append(c)

    # Fallback if filtering was too aggressive
    if not filtered:
        filtered = [t.text.lower() for t in doc if t.is_alpha and t.text.lower() not in _STOPWORDS]
        if not filtered:
            filtered = [query]

    # 6. Filter by semantic similarity (keep distinct vectors)
    embs = encoder.encode(filtered)
    if embs.ndim == 1:
        embs = embs.unsqueeze(0)
        
    embs_tensor = embs.cpu()
    
    keep = []
    for i, e in enumerate(embs_tensor):
        # Only keep if it is NOT highly similar to an already kept phrase
        if all(torch.cosine_similarity(e, embs_tensor[j], dim=0).item() < 0.9 for j in keep):
            keep.append(i)

    # 7. Final suppression of grammatical subphrases
    phrases = _suppress_subphrases([filtered[i] for i in keep])
    phrases = phrases[:8]  # Limit max phrases to prevent OT matrix bloat

    # Final embed
    final_embs = encoder.encode(phrases)
    if final_embs.ndim == 1:
        final_embs = final_embs.unsqueeze(0)
        
    return phrases, final_embs.cpu()

# --- OPTIMAL TRANSPORT STREAMING ---
def run_ot_selection_streaming(
    query_embs: torch.Tensor,
    sentence_records: List[SentenceRecord],
    mode: str,
    params: dict,
) -> Generator[dict, None, None]:
    """
    Generator that yields one event dict per selection step.
    The caller wraps this in an SSE response.
    """
    # Build candidate dicts that eviot expects
    candidates = [
        {"text": s.text, "emb": s.embedding, "_record": s}
        for s in sentence_records
    ]

    initial_cost = ot_cost(query_embs, torch.stack([s.embedding for s in sentence_records]))
    prev_cost = initial_cost
    selected_so_far = []
    remaining = candidates.copy()
    cumulative_tokens = 0

    epsilon = params.get("epsilon", 0.01)
    patience = params.get("patience", 2)
    k_max = params.get("k_max", 12)
    k_fixed = params.get("k", 5)

    no_gain_count = 0
    step = 0

    from eviot.selection.greedy import greedy_select

    while remaining and step < (k_fixed if mode == "fixed" else k_max):
        # Find best next candidate
        best, best_cost = greedy_select(query_embs, selected_so_far, remaining)

        marginal_gain = prev_cost - best_cost

        # Calculate absolute coverage
        coverage_pct = max(0.0, min(1.0, round(1.0 - best_cost, 4)))
        cumulative_tokens += len(best["text"].split())

        step += 1
        record: SentenceRecord = best["_record"]

        # 1. THIS MUST BE "selection_step"
        yield {
            "event": "selection_step",
            "step": step,
            "sentence_id": record.id,
            "sentence_text": best["text"],
            "source_doc": record.source_doc,
            "source_line": record.source_line,
            "ot_cost": round(best_cost, 6),
            "marginal_gain": round(marginal_gain, 6),
            "coverage_pct": coverage_pct,
            "cumulative_tokens": cumulative_tokens,
        }

        selected_so_far.append(best)
        remaining.remove(best)
        prev_cost = best_cost

        if mode == "fixed":
            if step >= k_fixed:
                break
        else:  # adaptive
            if marginal_gain < epsilon:
                no_gain_count += 1
            else:
                no_gain_count = 0
            if no_gain_count >= patience:
                # 2. Yield saturation when patience is exceeded
                yield {
                    "event": "saturation_reached",
                    "step": step,
                    "final_ot_cost": round(best_cost, 6),
                    "final_coverage_pct": coverage_pct,
                    "total_sentences_selected": step,
                    "total_tokens": cumulative_tokens,
                    "stopping_reason": f"marginal_gain_below_epsilon_for_{patience}_steps",
                }
                return

    # 3. Final fallback saturation yield (Fixed the coverage math here too)
    yield {
        "event": "saturation_reached",
        "step": step,
        "final_ot_cost": round(prev_cost, 6),
        "final_coverage_pct": max(0.0, min(1.0, round(1.0 - prev_cost, 4))),
        "total_sentences_selected": step,
        "total_tokens": cumulative_tokens,
        "stopping_reason": "fixed_k_reached" if mode == "fixed" else "k_max_reached",
    }