from __future__ import annotations

import numpy as np


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def mmr_rerank(
    candidates: list[tuple[str, float]],
    embeddings_by_id: dict[str, np.ndarray],
    k: int,
    lambda_param: float = 0.5,
) -> list[tuple[str, float]]:
    """Diversity-aware re-rank of a fused candidate list.

    Iteratively picks the next item maximizing
    `lambda * relevance - (1 - lambda) * max_similarity_to_already_picked`,
    so the final top-k is relevant but non-redundant (near-duplicate
    candidates get suppressed in favor of diverse, still-relevant ones).
    """
    if not candidates:
        return []

    ids = [c[0] for c in candidates]
    raw_scores = np.array([c[1] for c in candidates], dtype=float)
    lo, hi = raw_scores.min(), raw_scores.max()
    if hi > lo:
        norm_scores = (raw_scores - lo) / (hi - lo)
    else:
        norm_scores = np.ones_like(raw_scores)
    relevance = dict(zip(ids, norm_scores))

    selected: list[str] = []
    remaining = list(ids)

    while remaining and len(selected) < k:
        best_id, best_mmr = None, float("-inf")
        for candidate_id in remaining:
            rel = relevance[candidate_id]
            if selected:
                max_sim = max(
                    _cosine(embeddings_by_id[candidate_id], embeddings_by_id[s])
                    for s in selected
                )
            else:
                max_sim = 0.0
            mmr_score = lambda_param * rel - (1 - lambda_param) * max_sim
            if mmr_score > best_mmr:
                best_mmr, best_id = mmr_score, candidate_id
        selected.append(best_id)
        remaining.remove(best_id)

    return [(cid, relevance[cid]) for cid in selected]
