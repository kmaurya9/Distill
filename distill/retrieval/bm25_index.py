from __future__ import annotations

import bm25s
from bm25s.tokenization import Tokenizer


class BM25Index:
    """Lexical search over node text (name + docstring + content), per node id.

    Corpus and query must share one `Tokenizer` instance/vocab — tokenizing
    each independently (as in bm25s's simplest example) silently produces
    disjoint word->id mappings for a small corpus, making every query score 0.
    """

    def __init__(self) -> None:
        self.node_ids: list[str] = []
        self._retriever: bm25s.BM25 | None = None
        self._tokenizer = Tokenizer(stopwords="en")

    def build(self, node_ids: list[str], texts: list[str]) -> None:
        self.node_ids = list(node_ids)
        corpus_tokens = self._tokenizer.tokenize(texts, update_vocab=True, show_progress=False)
        self._retriever = bm25s.BM25()
        self._retriever.index(corpus_tokens, show_progress=False)

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        if self._retriever is None or not self.node_ids:
            return []
        k = min(k, len(self.node_ids))
        query_tokens = self._tokenizer.tokenize(
            [query], update_vocab=False, show_progress=False
        )
        results, scores = self._retriever.retrieve(query_tokens, k=k, show_progress=False)
        return [
            (self.node_ids[idx], float(score))
            for idx, score in zip(results[0], scores[0])
        ]
