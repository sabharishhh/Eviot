import torch
import re
from typing import Generator, List
from eviot.ot.cost import ot_cost
from session import SentenceRecord

_STOPWORDS = {
    "what", "how", "does", "do", "can", "is", "are",
    "the", "a", "an", "of", "in", "on", "for", "to", "with"
}

_INTERROGATIVES = {
    "what", "how", "does", "do", "can", "is", "are"
}

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
    Fixed local spaCy decomposition. Retains individual distinct keywords 
    alongside noun chunks to build a genuine multi-vector coverage footprint.
    
    Updated with a specificity filter to prune out generic single-word tokens.
    """
    from ingestion.chunker import get_nlp
    nlp = get_nlp()
    doc = nlp(query)
    
    candidates = []

    # 1. Grab noun chunks (e.g., "adoption agencies")
    for chunk in doc.noun_chunks:
        if len(_content_words(chunk)) >= 1:
            candidates.append(chunk.text)

    # 2. Grab strong unique nouns/proper nouns independently
    for token in doc:
        if token.pos_ in {"NOUN", "PROPN"} and token.text.lower() not in _STOPWORDS:
            candidates.append(token.text)

    # 3. Grab action verbs
    for token in doc:
        if token.pos_ == "VERB" and token.text.lower() not in _STOPWORDS:
            candidates.append(token.text)

    # Deduplicate string tokens while preserving insertion order
    seen = set()
    unique_phrases = []
    for c in candidates:
        norm_c = _normalize(c)
        if norm_c not in seen and len(norm_c) > 1:
            seen.add(norm_c)
            unique_phrases.append(norm_c)

    # Always seed with the full original query as the primary anchor
    normalized_query = _normalize(query)
    
    # --- STEP 6 FIX: SPECIFICITY FILTER ---
    filtered_phrases = []
    for phrase in unique_phrases:
        # Avoid treating single-word generic terms as independent transport targets
        words = phrase.split()
        if len(words) == 1 and len(words[0]) < 9:
            continue  # Drops 'identity' (8 chars), 'fields' (6 chars), etc.
            
        filtered_phrases.append(phrase)
        
    # Always ensure the full original query is seeded at index 0
    if normalized_query in filtered_phrases:
        filtered_phrases.remove(normalized_query)
    filtered_phrases.insert(0, normalized_query)
    
    # Take the top 5 surviving specific sub-phrase anchors
    phrases = filtered_phrases[:5] 
    # --------------------------------------

    if not phrases:
        phrases = [query]

    final_embs = encoder.encode(phrases)
    if final_embs.ndim == 1:
        final_embs = final_embs.unsqueeze(0)
        
    return phrases, final_embs.cpu()

def run_ot_selection_streaming(
    query_embs: torch.Tensor,
    sentence_records: List[SentenceRecord],
    mode: str,
    params: dict,
) -> Generator[dict, None, None]:
    """
    Generator that yields one event dict per selection step.
    The caller wraps this in an SSE response.
    
    Updated with Step 2 per-step OT diagnostics gated behind params.get("debug").
    """
    # 1. Look up configuration variables
    debug_mode = params.get("debug", False)
    epsilon = params.get("epsilon", 0.01)
    patience = params.get("patience", 2)
    k_max = params.get("k_max", 12)
    k_fixed = params.get("k", 5)

    # 2. Extract embedded candidates
    candidates = [
        {"text": s.text, "emb": s.embedding, "_record": s}
        for s in sentence_records
    ]

    # Pre-calculate the overall query intent centroid if diagnostics are enabled
    if debug_mode and query_embs is not None and query_embs.shape[0] > 0:
        # query_embs shape: (num_phrases, embedding_dim)
        query_centroid = query_embs.mean(dim=0, keepdim=True)
        query_centroid_norm = query_centroid / query_centroid.norm(dim=-1, keepdim=True)
    else:
        query_centroid_norm = None

    # Compute baseline distance mapping via our local OT distance module
    # (Assuming ot_cost is available in the current file scope or via an active local import)
    # If ot_cost expects torch tensors, convert the stack accordingly
    # all_embs = torch.stack([torch.tensor(s.embedding, dtype=torch.float32) for s in sentence_records])
    # all_embs = torch.stack([torch.tensor(s.embedding, dtype=torch.float32).detach().clone() for s in sentence_records])
    all_embs = torch.stack([s.embedding.detach().clone().to(torch.float32) for s in sentence_records])
    initial_cost = ot_cost(query_embs, all_embs)
    
    prev_cost = initial_cost
    selected_so_far = []
    remaining = candidates.copy()
    cumulative_tokens = 0

    no_gain_count = 0
    step = 0

    from eviot.selection.greedy import greedy_select

    while remaining and step < (k_fixed if mode == "fixed" else k_max):
        # Determine the single best candidate for this optimization block
        best, best_cost = greedy_select(query_embs, selected_so_far, remaining)
        marginal_gain = prev_cost - best_cost

        # 3. COMPUTE STEP 2 PER-STEP DIAGNOSTICS PRIOR TO MODIFIED ARRAY MUTATIONS
        if debug_mode and query_centroid_norm is not None:
            candidates_scores = []
            
            for item in remaining:
                rec_obj: SentenceRecord = item["_record"]
                
                # Stack item vector and normalize
                cand_tensor = torch.tensor(item["emb"], dtype=torch.float32).view(1, -1)
                cand_norm = cand_tensor / cand_tensor.norm(dim=-1, keepdim=True)
                
                # Calculate cosine similarity directly against the central query anchor
                cosine_to_centroid = torch.mm(cand_norm, query_centroid_norm.T).item()
                
                # Score potential step context using greedy_select logic
                # We simulate this item's temporary selection to find its actual step ot_cost & marginal_gain
                _, item_step_cost = greedy_select(query_embs, selected_so_far, [item])
                item_marginal_gain = prev_cost - item_step_cost
                
                candidates_scores.append({
                    "id": rec_obj.id,
                    "ot_cost": round(float(item_step_cost), 4),
                    "cosine_to_centroid": round(cosine_to_centroid, 4),
                    "marginal_gain": round(float(item_marginal_gain), 4)
                })
            
            # Sort full candidate checklist by highest step marginal gain to fetch the definitive top 5
            candidates_scores.sort(key=lambda x: x["marginal_gain"], reverse=True)
            top_5_diagnostics = [
                (c["id"], c["ot_cost"], c["cosine_to_centroid"]) 
                for c in candidates_scores[:5]
            ]
            
            # Print explicit visibility trace directly to the backend logging standard out
            print(
                f"[OT_DEBUG] Step {step} | "
                f"Top-5 Candidates: {top_5_diagnostics} | "
                f"Selected: '{best['_record'].id}' | "
                f"Marginal Gain: {round(float(marginal_gain), 4)}"
            )

        # 4. Standard production yield and state preservation
        coverage_pct = max(0.0, min(1.0, round(1.0 - best_cost, 4)))
        cumulative_tokens += len(best["text"].split())

        step += 1
        record: SentenceRecord = best["_record"]

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
        remaining[:] = [c for c in remaining if c is not best]
        prev_cost = best_cost

        if mode == "fixed":
            if step >= k_fixed:
                break
        else: 
            if marginal_gain < epsilon:
                no_gain_count += 1
            else:
                no_gain_count = 0
            if no_gain_count >= patience:
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

    yield {
        "event": "saturation_reached",
        "step": step,
        "final_ot_cost": round(prev_cost, 6),
        "final_coverage_pct": max(0.0, min(1.0, round(1.0 - prev_cost, 4))),
        "total_sentences_selected": step,
        "total_tokens": cumulative_tokens,
        "stopping_reason": "fixed_k_reached" if mode == "fixed" else "k_max_reached",
    }