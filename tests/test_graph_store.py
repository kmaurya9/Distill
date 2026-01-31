from distill.indexing.graph_builder import GraphEdge, GraphNode
from distill.store.graph_store import GraphStore


def _node(node_id: str, name: str = "n") -> GraphNode:
    return GraphNode(
        id=node_id,
        kind="FUNCTION",
        name=name,
        file_path="a.py",
        language="python",
        start_line=1,
        end_line=2,
        docstring=None,
        content_hash="hash-" + node_id,
    )


def test_upsert_and_count(tmp_path):
    store = GraphStore(tmp_path / "graph.db")
    store.upsert_nodes([_node("a"), _node("b")])
    store.insert_edges([GraphEdge(src_id="a", dst_id="b", kind="CALLS")])

    assert store.node_count() == 2
    assert store.edge_count() == 1
    assert store.get_node("a").name == "n"
    store.close()


def test_clear_file_removes_nodes_and_edges(tmp_path):
    store = GraphStore(tmp_path / "graph.db")
    node_a = _node("a")
    node_b = _node("b")
    node_b.file_path = "b.py"
    store.upsert_nodes([node_a, node_b])
    store.insert_edges([GraphEdge(src_id="a", dst_id="b", kind="CALLS")])

    store.clear_file("a.py")

    assert store.node_count() == 1
    assert store.edge_count() == 0
    store.close()


def test_cache_roundtrip(tmp_path):
    store = GraphStore(tmp_path / "graph.db")
    store.cache_put("h1", '{"x": 1}', b"\x00\x01")
    parsed_json, embedding = store.cache_get("h1")
    assert parsed_json == '{"x": 1}'
    assert embedding == b"\x00\x01"
    assert store.cache_get("missing") is None
    store.close()
