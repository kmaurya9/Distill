from __future__ import annotations

import numpy as np


class EmbeddingModel:
    """Pluggable embedding backend. Default: local sentence-transformers model
    (no API key required, self-contained install). Swappable for OpenAI or
    another provider without changing callers — they only see .encode()."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        embeddings = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings.astype("float32")
