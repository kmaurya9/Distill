"""Retrieval-quality evaluation (claim #14): recall@k and MRR for BM25-only,
embeddings-only, and the full fused+PageRank+RRF+MMR pipeline, against a
hand-labeled query set (eval/dataset/queries.json).

Each label was found by grepping the real target corpus for a well-known
function, reading its actual implementation to confirm it answers the
query, then looking up its real node id in the indexed graph — not guessed.

Usage: python eval/run_eval.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from distill.indexing.multi_repo import build_multi_repo
from distill.retrieval.embeddings import EmbeddingModel
from distill.retrieval.pipeline import RetrievalIndex
from distill.store.graph_store import GraphStore

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPORA = REPO_ROOT / "corpora"
QUERIES_PATH = Path(__file__).resolve().parent / "dataset" / "queries.json"
EVAL_REPOS = ["flask", "express"]
K_VALUES = (1, 5, 10)
MRR_CUTOFF = 50


def load_queries() -> list[dict]:
    return json.loads(QUERIES_PATH.read_text())


def resolve_expected_node_id(store: GraphStore, q: dict) -> str:
    matches = [
        n
        for n in store.all_nodes()
        if n.file_path == q["file_path"] and n.name == q["name"] and n.start_line == q["start_line"]
    ]
    if not matches:
        raise ValueError(f"Label not found in index: {q}")
    return matches[0].id


def recall_at_k(ranked_ids: list[str], expected_id: str, k: int) -> bool:
    return expected_id in ranked_ids[:k]


def reciprocal_rank(ranked_ids: list[str], expected_id: str, cutoff: int) -> float:
    for rank, node_id in enumerate(ranked_ids[:cutoff], start=1):
        if node_id == expected_id:
            return 1.0 / rank
    return 0.0


def main() -> None:
    print(f"Building eval corpus from {EVAL_REPOS} ...")
    t0 = time.time()
    nodes, edges = build_multi_repo([CORPORA / r for r in EVAL_REPOS])
    store = GraphStore(REPO_ROOT / "eval" / "eval_corpus.db")
    store.clear()
    store.upsert_nodes(nodes)
    store.insert_edges(edges)
    print(f"  {store.node_count()} nodes, {store.edge_count()} edges ({time.time() - t0:.1f}s)")

    print("Building retrieval index (BM25 + embeddings + PageRank) ...")
    t0 = time.time()
    embedding_model = EmbeddingModel()
    index = RetrievalIndex(embedding_model=embedding_model)
    index.build(nodes, edges, CORPORA)
    print(f"  done ({time.time() - t0:.1f}s)")

    queries = load_queries()
    expected_ids = {q["query"]: resolve_expected_node_id(store, q) for q in queries}
    print(f"Loaded {len(queries)} labeled queries.\n")

    configs = ["bm25_only", "embeddings_only", "full_pipeline"]
    ranked_lists: dict[str, dict[str, list[str]]] = {c: {} for c in configs}

    for q in queries:
        query_text = q["query"]

        bm25_ranked = [nid for nid, _ in index.bm25.search(query_text, k=MRR_CUTOFF)]
        ranked_lists["bm25_only"][query_text] = bm25_ranked

        query_embedding = embedding_model.encode([query_text])[0]
        dense_ranked = [nid for nid, _ in index.vector_store.search(query_embedding, k=MRR_CUTOFF)]
        ranked_lists["embeddings_only"][query_text] = dense_ranked

        full_ranked = [nid for nid, _ in index.search(query_text, k=MRR_CUTOFF)]
        ranked_lists["full_pipeline"][query_text] = full_ranked

    print(f"{'config':<18}" + "".join(f"recall@{k:<8}" for k in K_VALUES) + "MRR")
    results = {}
    for config in configs:
        recalls = {
            k: sum(
                recall_at_k(ranked_lists[config][q["query"]], expected_ids[q["query"]], k)
                for q in queries
            )
            / len(queries)
            for k in K_VALUES
        }
        mrr = sum(
            reciprocal_rank(ranked_lists[config][q["query"]], expected_ids[q["query"]], MRR_CUTOFF)
            for q in queries
        ) / len(queries)
        results[config] = {"recall": recalls, "mrr": mrr}
        row = f"{config:<18}" + "".join(f"{recalls[k]:<16.2f}" for k in K_VALUES) + f"{mrr:.3f}"
        print(row)

    store.close()


if __name__ == "__main__":
    main()
