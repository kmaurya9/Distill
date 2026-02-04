from __future__ import annotations

import faiss
import numpy as np


class VectorStore:
    """Embedded FAISS index (cosine similarity via inner product on
    normalized vectors), keyed by node id — no server required."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._index = faiss.IndexFlatIP(dim)
        self.node_ids: list[str] = []

    def build(self, node_ids: list[str], embeddings: np.ndarray) -> None:
        self.node_ids = list(node_ids)
        self._index = faiss.IndexFlatIP(self.dim)
        if len(node_ids):
            self._index.add(embeddings)

    def search(self, query_embedding: np.ndarray, k: int = 10) -> list[tuple[str, float]]:
        if not self.node_ids:
            return []
        k = min(k, len(self.node_ids))
        scores, indices = self._index.search(query_embedding.reshape(1, -1), k)
        return [
            (self.node_ids[idx], float(score))
            for idx, score in zip(indices[0], scores[0])
            if idx != -1
        ]
