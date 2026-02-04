import pytest

from distill.retrieval.fusion import apply_pagerank_prior, reciprocal_rank_fusion


def test_rrf_matches_hand_computed_toy_case():
    # k=1 for easy-to-check arithmetic.
    list_a = ["a", "b", "c"]
    list_b = ["b", "a", "d"]

    result = reciprocal_rank_fusion([list_a, list_b], k=1)
    scores = dict(result)

    # a: rank 1 in A (1/2) + rank 2 in B (1/3) = 5/6
    assert scores["a"] == pytest.approx(1 / 2 + 1 / 3)
    # b: rank 2 in A (1/3) + rank 1 in B (1/2) = 5/6
    assert scores["b"] == pytest.approx(1 / 3 + 1 / 2)
    # c: rank 3 in A only = 1/4
    assert scores["c"] == pytest.approx(1 / 4)
    # d: rank 3 in B only = 1/4
    assert scores["d"] == pytest.approx(1 / 4)

    # a and b tie for first (both appear near the top of both lists)
    top_two = {result[0][0], result[1][0]}
    assert top_two == {"a", "b"}


def test_rrf_respects_weights():
    list_a = ["x", "y"]
    list_b = ["y", "x"]
    result = reciprocal_rank_fusion([list_a, list_b], k=0, weights=[10.0, 1.0])
    scores = dict(result)
    # x: rank1 in A (weight 10 * 1/1) + rank2 in B (weight 1 * 1/2)
    assert scores["x"] == pytest.approx(10.0 * 1 + 1.0 * (1 / 2))
    assert scores["x"] > scores["y"]


def test_pagerank_prior_boosts_high_centrality_node():
    fused = [("low_pr", 1.0), ("high_pr", 0.9)]
    pagerank_scores = {"low_pr": 0.01, "high_pr": 0.5}
    combined = apply_pagerank_prior(fused, pagerank_scores, alpha=1.0)
    assert combined[0][0] == "high_pr"
