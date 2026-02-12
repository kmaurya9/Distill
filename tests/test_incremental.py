from distill.indexing.cache import ParseCache
from distill.indexing.incremental import IncrementalIndexer
from distill.store.graph_store import GraphStore


def test_modifying_one_file_only_reparses_and_touches_that_file(tmp_path):
    (tmp_path / "a.py").write_text("def a_fn():\n    return 1\n")
    (tmp_path / "b.py").write_text("def b_fn():\n    return 2\n")

    store = GraphStore(tmp_path / "graph.db")
    parse_cache = ParseCache(store)
    indexer = IncrementalIndexer(store, parse_cache=parse_cache)

    first_report = indexer.reindex(tmp_path)
    assert sorted(first_report.new_files) == ["a.py", "b.py"]
    b_fn_before = store.get_node(
        next(n.id for n in store.all_nodes() if n.name == "b_fn")
    )

    # modify only a.py
    (tmp_path / "a.py").write_text("def a_fn():\n    return 999\n")

    second_report = indexer.reindex(tmp_path)
    assert second_report.changed_files == ["a.py"]
    assert second_report.unchanged_files == ["b.py"]

    # b.py's content was already in the parse cache from the first run -
    # re-indexing does not re-parse it.
    assert indexer.last_parse_cache_hits == 1  # b.py
    assert indexer.last_parse_cache_misses == 1  # a.py (new content)

    b_fn_after = store.get_node(
        next(n.id for n in store.all_nodes() if n.name == "b_fn")
    )
    assert b_fn_after == b_fn_before  # completely untouched

    a_fn_node = next(n for n in store.all_nodes() if n.name == "a_fn")
    # the a.py FILE node's content_hash reflects the new content
    a_file_node = next(
        n for n in store.all_nodes() if n.file_path == "a.py" and n.kind == "FILE"
    )
    assert a_file_node.content_hash != b_fn_before.content_hash
    store.close()


def test_deleted_file_removed_from_store(tmp_path):
    (tmp_path / "a.py").write_text("def a_fn():\n    return 1\n")
    (tmp_path / "b.py").write_text("def b_fn():\n    return 2\n")

    store = GraphStore(tmp_path / "graph.db")
    indexer = IncrementalIndexer(store)
    indexer.reindex(tmp_path)

    (tmp_path / "b.py").unlink()
    report = indexer.reindex(tmp_path)

    assert report.deleted_files == ["b.py"]
    assert not any(n.file_path == "b.py" for n in store.all_nodes())
    assert any(n.file_path == "a.py" for n in store.all_nodes())
    store.close()


def test_new_file_added_to_store(tmp_path):
    (tmp_path / "a.py").write_text("def a_fn():\n    return 1\n")
    store = GraphStore(tmp_path / "graph.db")
    indexer = IncrementalIndexer(store)
    indexer.reindex(tmp_path)

    (tmp_path / "c.py").write_text("def c_fn():\n    return 3\n")
    report = indexer.reindex(tmp_path)

    assert report.new_files == ["c.py"]
    assert any(n.name == "c_fn" for n in store.all_nodes())
    store.close()
