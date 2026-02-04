import pytest

from distill.indexing.graph_builder import GraphBuilder
from distill.retrieval.embeddings import EmbeddingModel
from distill.retrieval.pipeline import RetrievalIndex


@pytest.fixture(scope="module")
def embedding_model():
    return EmbeddingModel()


def test_end_to_end_query_returns_relevant_node(tmp_path, embedding_model):
    (tmp_path / "auth.py").write_text(
        "def validate_auth_token(token):\n"
        "    # Validate the auth token before letting the request through.\n"
        "    return token is not None\n"
    )
    (tmp_path / "render.py").write_text(
        "def render_template(name, context):\n"
        "    return f'<html>{name}</html>'\n"
    )
    (tmp_path / "checksum.py").write_text(
        "def compute_checksum(data):\n"
        "    return sum(data) % 251\n"
    )
    (tmp_path / "parse.py").write_text(
        "def parse_json_body(request):\n"
        "    return request.body\n"
    )

    nodes, edges = GraphBuilder().build(tmp_path)
    index = RetrievalIndex(embedding_model=embedding_model)
    index.build(nodes, edges, tmp_path)

    results = index.query("how do we validate the auth token?", k=4)
    assert results
    top_node_id = results[0][0]
    top_node = next(n for n in nodes if n.id == top_node_id)
    assert top_node.name == "validate_auth_token"
