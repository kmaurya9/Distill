"""Content-addressed caching for parse results and embeddings (claim #13).

Both caches are keyed by `hash(content)` — identical content at a different
path (or a different commit, or a copy/paste duplicate) is a cache hit, not
recomputed. Backed by GraphStore's `cache` table (content_hash -> parsed_json,
embedding blob).
"""

from __future__ import annotations

import json

import numpy as np

from distill.indexing.parsers.base import CallSite, FileExtraction, RawImport, Symbol
from distill.store.graph_store import GraphStore


class ParseCache:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def get(self, content_hash: str) -> FileExtraction | None:
        row = self.store.cache_get(content_hash)
        if row is None:
            return None
        parsed_json, _ = row
        if parsed_json is None:
            return None
        data = json.loads(parsed_json)
        symbols = [
            Symbol(
                kind=s["kind"],
                name=s["name"],
                start_line=s["start_line"],
                end_line=s["end_line"],
                node=None,
                parent_name=s["parent_name"],
                start_byte=s["start_byte"],
                end_byte=s["end_byte"],
            )
            for s in data["symbols"]
        ]
        calls = [CallSite(**c) for c in data["calls"]]
        imports = [RawImport(**i) for i in data["imports"]]
        return FileExtraction(symbols=symbols, calls=calls, imports=imports)

    def put(self, content_hash: str, extraction: FileExtraction) -> None:
        data = {
            "symbols": [
                {
                    "kind": s.kind,
                    "name": s.name,
                    "start_line": s.start_line,
                    "end_line": s.end_line,
                    "parent_name": s.parent_name,
                    "start_byte": s.start_byte,
                    "end_byte": s.end_byte,
                }
                for s in extraction.symbols
            ],
            "calls": [{"caller_name": c.caller_name, "callee_name": c.callee_name} for c in extraction.calls],
            "imports": [{"module": i.module} for i in extraction.imports],
        }
        existing = self.store.cache_get(content_hash)
        embedding = existing[1] if existing else None
        self.store.cache_put(content_hash, json.dumps(data), embedding)


class EmbeddingCache:
    def __init__(self, store: GraphStore, dim: int) -> None:
        self.store = store
        self.dim = dim

    def get(self, content_hash: str) -> np.ndarray | None:
        row = self.store.cache_get(content_hash)
        if row is None:
            return None
        _, blob = row
        if blob is None:
            return None
        return np.frombuffer(blob, dtype="float32")

    def put(self, content_hash: str, vector: np.ndarray) -> None:
        existing = self.store.cache_get(content_hash)
        parsed_json = existing[0] if existing else None
        self.store.cache_put(content_hash, parsed_json, vector.astype("float32").tobytes())
