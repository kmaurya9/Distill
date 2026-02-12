import pytest

from distill.indexing.cache import EmbeddingCache
from distill.indexing.graph_builder import GraphBuilder
from distill.retrieval.embeddings import EmbeddingModel
from distill.retrieval.pipeline import RetrievalIndex
from distill.store.graph_store import GraphStore


@pytest.fixture(scope="module")
def embedding_model():
    return EmbeddingModel()


def test_identical_function_body_at_different_path_is_embedding_cache_hit(tmp_path, embedding_model):
    body = "def helper():\n    return 1\n"
    (tmp_path / "a.py").write_text(body)
    (tmp_path / "b.py").write_text(body)  # identical content, different path/name irrelevant

    nodes, edges = GraphBuilder().build(tmp_path)
    store = GraphStore(tmp_path / "cache.db")
    embedding_cache = EmbeddingCache(store, dim=embedding_model.dim)

    index = RetrievalIndex(embedding_model=embedding_model)
    index.build(nodes, edges, tmp_path, embedding_cache=embedding_cache)

    assert index.embedding_cache_misses == 1
    assert index.embedding_cache_hits == 1
    store.close()
