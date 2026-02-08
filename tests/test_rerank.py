import numpy as np

from distill.retrieval.rerank import mmr_rerank


def test_suppresses_near_duplicate_in_favor_of_diverse_result():
    candidates = [("a", 0.9), ("dup_of_a", 0.85), ("b", 0.6)]
    embeddings = {
        "a": np.array([1.0, 0.0]),
        "dup_of_a": np.array([0.99, 0.05]),  # near-duplicate direction of "a"
        "b": np.array([0.0, 1.0]),  # orthogonal / diverse
    }

    result = mmr_rerank(candidates, embeddings, k=2, lambda_param=0.5)
    ids = [r[0] for r in result]

    assert ids[0] == "a"
    assert "b" in ids
    assert "dup_of_a" not in ids


def test_returns_at_most_k_and_keeps_sole_candidate():
    candidates = [("only", 1.0)]
    embeddings = {"only": np.array([1.0, 0.0])}
    result = mmr_rerank(candidates, embeddings, k=5)
    assert [r[0] for r in result] == ["only"]
