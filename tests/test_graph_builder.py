import textwrap

from distill.indexing.graph_builder import GraphBuilder


def _write(tmp_path, rel_path: str, content: str):
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
    return path


def test_builds_nodes_and_contains_edges(tmp_path):
    _write(
        tmp_path,
        "pkg/a.py",
        """
        class Widget:
            def render(self):
                return helper()

        def helper():
            return 1
        """,
    )
    nodes, edges = GraphBuilder().build(tmp_path)

    kinds = {(n.kind, n.name) for n in nodes}
    assert ("FILE", "a.py") in kinds
    assert ("CLASS", "Widget") in kinds
    assert ("FUNCTION", "render") in kinds
    assert ("FUNCTION", "helper") in kinds

    contains = {(e.src_id, e.dst_id) for e in edges if e.kind == "CONTAINS"}
    file_node = next(n for n in nodes if n.kind == "FILE")
    class_node = next(n for n in nodes if n.kind == "CLASS")
    render_node = next(n for n in nodes if n.name == "render")
    helper_node = next(n for n in nodes if n.name == "helper")

    assert (file_node.id, class_node.id) in contains
    assert (class_node.id, render_node.id) in contains
    assert (file_node.id, helper_node.id) in contains


def test_resolves_calls_across_functions(tmp_path):
    _write(
        tmp_path,
        "m.py",
        """
        def a():
            return b()

        def b():
            return 1
        """,
    )
    nodes, edges = GraphBuilder().build(tmp_path)
    a_node = next(n for n in nodes if n.name == "a")
    b_node = next(n for n in nodes if n.name == "b")
    calls = {(e.src_id, e.dst_id) for e in edges if e.kind == "CALLS"}
    assert (a_node.id, b_node.id) in calls


def test_resolves_imports_across_files(tmp_path):
    _write(tmp_path, "pkg/util.py", "def helper():\n    return 1\n")
    _write(tmp_path, "pkg/main.py", "from pkg import util\n")

    nodes, edges = GraphBuilder().build(tmp_path)
    util_file = next(n for n in nodes if n.file_path == "pkg/util.py" and n.kind == "FILE")
    main_file = next(n for n in nodes if n.file_path == "pkg/main.py" and n.kind == "FILE")
    imports = {(e.src_id, e.dst_id) for e in edges if e.kind == "IMPORTS"}
    assert (main_file.id, util_file.id) in imports


def test_skips_ignored_directories(tmp_path):
    _write(tmp_path, "node_modules/dep/index.js", "function x() { return 1; }\n")
    _write(tmp_path, "src/app.js", "function y() { return 2; }\n")

    nodes, _ = GraphBuilder().build(tmp_path)
    file_paths = {n.file_path for n in nodes}
    assert "src/app.js" in file_paths
    assert not any("node_modules" in p for p in file_paths)
