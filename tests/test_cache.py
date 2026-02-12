import numpy as np

from distill.indexing.cache import EmbeddingCache, ParseCache
from distill.indexing.graph_builder import GraphBuilder
from distill.indexing.parsers.base import CallSite, FileExtraction, RawImport, Symbol
from distill.store.graph_store import GraphStore


def _extraction() -> FileExtraction:
    return FileExtraction(
        symbols=[
            Symbol(kind="FUNCTION", name="helper", start_line=1, end_line=2, node=None, start_byte=0, end_byte=20)
        ],
        calls=[CallSite(caller_name="a", callee_name="b")],
        imports=[RawImport(module="os")],
    )


def test_parse_cache_roundtrip(tmp_path):
    store = GraphStore(tmp_path / "g.db")
    cache = ParseCache(store)
    assert cache.get("h1") is None

    extraction = _extraction()
    cache.put("h1", extraction)

    restored = cache.get("h1")
    assert restored is not None
    assert restored.symbols[0].name == "helper"
    assert restored.symbols[0].start_byte == 0
    assert restored.symbols[0].end_byte == 20
    assert restored.calls[0].callee_name == "b"
    assert restored.imports[0].module == "os"
    store.close()


def test_embedding_cache_roundtrip(tmp_path):
    store = GraphStore(tmp_path / "g.db")
    cache = EmbeddingCache(store, dim=4)
    assert cache.get("h1") is None

    vec = np.array([0.1, 0.2, 0.3, 0.4], dtype="float32")
    cache.put("h1", vec)

    restored = cache.get("h1")
    assert np.allclose(restored, vec)
    store.close()


def test_identical_content_at_different_path_is_cache_hit(tmp_path):
    content = "def helper():\n    return 1\n"
    (tmp_path / "a.py").write_text(content)
    (tmp_path / "b.py").write_text(content)  # duplicate content, different path

    store = GraphStore(tmp_path / "cache.db")
    parse_cache = ParseCache(store)
    builder = GraphBuilder(parse_cache=parse_cache)
    builder.build(tmp_path)

    assert builder.cache_misses == 1  # first file parsed for real
    assert builder.cache_hits == 1  # second file's identical content reused
    store.close()


def test_reindexing_unchanged_repo_is_all_cache_hits(tmp_path):
    (tmp_path / "a.py").write_text("def helper():\n    return 1\n")
    (tmp_path / "b.py").write_text("def other():\n    return 2\n")

    store = GraphStore(tmp_path / "cache.db")
    parse_cache = ParseCache(store)

    first = GraphBuilder(parse_cache=parse_cache)
    first.build(tmp_path)
    assert first.cache_misses == 2
    assert first.cache_hits == 0

    second = GraphBuilder(parse_cache=parse_cache)
    second.build(tmp_path)
    assert second.cache_hits == 2
    assert second.cache_misses == 0
    store.close()
