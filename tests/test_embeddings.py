import pytest

from distill.retrieval.embeddings import EmbeddingModel
from distill.store.vector_store import VectorStore


@pytest.fixture(scope="module")
def model():
    return EmbeddingModel()


def test_semantically_similar_snippet_scores_highest(model):
    node_ids = ["file_exists", "unrelated_add"]
    texts = [
        "def path_exists(p):\n    return os.path.exists(p)",
        "def add(a, b):\n    return a + b",
    ]
    embeddings = model.encode(texts)

    store = VectorStore(dim=model.dim)
    store.build(node_ids, embeddings)

    query_embedding = model.encode(["how do I check whether a file exists on disk"])[0]
    results = store.search(query_embedding, k=2)

    assert results[0][0] == "file_exists"
    assert results[0][1] > results[1][1]
