from __future__ import annotations

from pathlib import Path

import numpy as np

from distill.indexing.graph_builder import GraphEdge, GraphNode
from distill.retrieval.bm25_index import BM25Index
from distill.retrieval.embeddings import EmbeddingModel
from distill.retrieval.fusion import apply_pagerank_prior, reciprocal_rank_fusion
from distill.retrieval.pagerank import compute_pagerank
from distill.retrieval.rerank import mmr_rerank
from distill.store.snippets import SnippetReader
from distill.store.vector_store import VectorStore


class RetrievalIndex:
    """Ties BM25 + dense embeddings + PageRank + RRF into one queryable index
    over a repo's code graph. MMR re-ranking (Phase 3) is layered on top of
    `query()`'s fused results, not inside this class."""

    def __init__(self, embedding_model: EmbeddingModel | None = None) -> None:
        self.embedding_model = embedding_model or EmbeddingModel()
        self.node_ids: list[str] = []
        self.bm25 = BM25Index()
        self.vector_store: VectorStore | None = None
        self.pagerank_scores: dict[str, float] = {}
        self.embeddings_by_id: dict[str, np.ndarray] = {}
        self.texts_by_id: dict[str, str] = {}

    def build(self, nodes: list[GraphNode], edges: list[GraphEdge], repo_root: str | Path) -> None:
        # PageRank runs over the full graph (FILE-FILE via IMPORTS, FUNCTION-
        # FUNCTION via CALLS are disjoint components either way). Retrieval
        # candidates are CLASS/FUNCTION nodes only — a whole FILE is rarely a
        # useful "snippet," and for small files it's a near-duplicate of the
        # one symbol it contains, which would just confuse ranking.
        self.pagerank_scores = compute_pagerank(nodes, edges)
        retrieval_nodes = [n for n in nodes if n.kind in ("CLASS", "FUNCTION")]

        reader = SnippetReader(repo_root)
        self.node_ids = [n.id for n in retrieval_nodes]
        texts = []
        for n in retrieval_nodes:
            snippet = reader.read(n)
            texts.append(f"{n.name}\n{snippet}")
        self.texts_by_id = dict(zip(self.node_ids, texts))

        self.bm25.build(self.node_ids, texts)

        embeddings = self.embedding_model.encode(texts)
        self.vector_store = VectorStore(dim=self.embedding_model.dim)
        self.vector_store.build(self.node_ids, embeddings)
        self.embeddings_by_id = dict(zip(self.node_ids, embeddings))

    def query(
        self,
        text: str,
        k: int = 10,
        candidate_k: int | None = None,
        pagerank_alpha: float = 0.5,
    ) -> list[tuple[str, float]]:
        if not self.node_ids:
            return []
        candidate_k = candidate_k or min(max(k * 5, 50), len(self.node_ids))

        bm25_ranked = [nid for nid, _ in self.bm25.search(text, k=candidate_k)]

        query_embedding = self.embedding_model.encode([text])[0]
        dense_ranked = [nid for nid, _ in self.vector_store.search(query_embedding, k=candidate_k)]

        fused = reciprocal_rank_fusion([bm25_ranked, dense_ranked])
        fused = apply_pagerank_prior(fused, self.pagerank_scores, alpha=pagerank_alpha)
        return fused[:k]

    def search(
        self,
        text: str,
        k: int = 10,
        candidate_k: int | None = None,
        pagerank_alpha: float = 0.5,
        mmr_lambda: float = 0.5,
    ) -> list[tuple[str, float]]:
        """Fused ranking, then MMR re-ranked for a small, non-redundant top-k
        — this is what `search_code` (the MCP tool) calls."""
        pool_size = max(k * 4, 20)
        fused = self.query(text, k=pool_size, candidate_k=candidate_k, pagerank_alpha=pagerank_alpha)
        return mmr_rerank(fused, self.embeddings_by_id, k=k, lambda_param=mmr_lambda)
