from distill.indexing.graph_builder import GraphNode
from distill.store.snippets import SnippetReader


def test_reads_line_range(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\nline3\nline4\n")
    node = GraphNode(
        id="a.py::x::2", kind="FUNCTION", name="x", file_path="a.py", language="python",
        start_line=2, end_line=3, docstring=None, content_hash="h",
    )
    reader = SnippetReader(tmp_path)
    assert reader.read(node) == "line2\nline3"
