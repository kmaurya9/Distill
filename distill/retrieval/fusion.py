from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    """Combine several ranked lists of node ids into one ranking.

    Each list contributes 1 / (k + rank) per item (rank is 1-indexed);
    contributions from all lists are summed per node id. Higher score first.
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights must match ranked_lists length")

    scores: dict[str, float] = defaultdict(float)
    for weight, ranked in zip(weights, ranked_lists):
        for rank, node_id in enumerate(ranked, start=1):
            scores[node_id] += weight * (1.0 / (k + rank))

    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def apply_pagerank_prior(
    fused: list[tuple[str, float]],
    pagerank_scores: dict[str, float],
    alpha: float = 1.0,
) -> list[tuple[str, float]]:
    """Add an alpha-weighted PageRank prior on top of fused RRF scores."""
    combined = [
        (node_id, score + alpha * pagerank_scores.get(node_id, 0.0))
        for node_id, score in fused
    ]
    return sorted(combined, key=lambda pair: pair[1], reverse=True)
