from distill.indexing.graph_builder import GraphEdge, GraphNode
from distill.retrieval.pagerank import compute_pagerank


def _fn(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id, kind="FUNCTION", name=node_id, file_path="a.py", language="python",
        start_line=1, end_line=2, docstring=None, content_hash="h" + node_id,
    )


def test_heavily_called_utility_outranks_leaf_function():
    nodes = [_fn("shared_util"), _fn("caller_a"), _fn("caller_b"), _fn("caller_c"), _fn("leaf")]
    edges = [
        GraphEdge(src_id="caller_a", dst_id="shared_util", kind="CALLS"),
        GraphEdge(src_id="caller_b", dst_id="shared_util", kind="CALLS"),
        GraphEdge(src_id="caller_c", dst_id="shared_util", kind="CALLS"),
    ]

    scores = compute_pagerank(nodes, edges)

    assert scores["shared_util"] > scores["leaf"]
    assert scores["shared_util"] > scores["caller_a"]


def test_no_edges_returns_uniform_scores():
    nodes = [_fn("a"), _fn("b")]
    scores = compute_pagerank(nodes, [])
    assert scores["a"] == scores["b"] == 0.5
