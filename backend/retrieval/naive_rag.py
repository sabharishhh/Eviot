import torch
from typing import List
from session import SentenceRecord

def naive_top_k(
    query_embs: torch.Tensor,
    sentence_records: List[SentenceRecord],
    k: int,
) -> list[dict]:
    """Cosine similarity top-k retrieval baseline."""

    q_centroid = query_embs.mean(dim=0)
    
    scored = []
    for rec in sentence_records:
        sim = torch.cosine_similarity(q_centroid, rec.embedding, dim=0).item()
        scored.append((rec, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:k]
    
    return [
        {
            "sentence_id": rec.id,
            "sentence_text": rec.text,
            "source_doc": rec.source_doc,
            "source_line": rec.source_line,
            "cosine_similarity": round(sim, 4),
        }
        for rec, sim in top
    ]

def compute_internal_redundancy(embeddings: List[torch.Tensor]) -> float:
    """Average pairwise cosine similarity within a set (higher = more redundant)."""
    if len(embeddings) <= 1:
        return 0.0
    total, count = 0.0, 0
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            total += torch.cosine_similarity(embeddings[i], embeddings[j], dim=0).item()
            count += 1
    return round(total / count, 4) if count > 0 else 0.0