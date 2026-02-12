"""Incremental re-indexing (claim #12): only new/changed/deleted files touch
the store on a re-run; everything else is left exactly as it was.

Change detection compares each file's current content hash against the hash
stored on its FILE node (not mtime — content hash is robust to checkouts,
copies, and clock skew, and reuses the same mechanism as content-addressed
caching). A full in-memory graph pass still runs each time (CALLS/IMPORTS
resolution is inherently repo-wide), but the *parse* step for unchanged files
is skipped via ParseCache, and only touched files' nodes are written back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from distill.indexing.cache import ParseCache
from distill.indexing.graph_builder import GraphBuilder, iter_source_files
from distill.indexing.parsers.base import content_hash
from distill.store.graph_store import GraphStore


@dataclass
class IncrementalReport:
    new_files: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    unchanged_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)


class IncrementalIndexer:
    def __init__(self, store: GraphStore, parse_cache: ParseCache | None = None) -> None:
        self.store = store
        self.parse_cache = parse_cache

    def reindex(self, repo_root: str | Path) -> IncrementalReport:
        repo_root = Path(repo_root).resolve()

        existing_file_hashes = {
            n.file_path: n.content_hash for n in self.store.all_nodes() if n.kind == "FILE"
        }

        current_files: dict[str, str] = {}
        for path in iter_source_files(repo_root):
            rel_path = path.relative_to(repo_root).as_posix()
            try:
                source = path.read_bytes()
            except OSError:
                continue
            current_files[rel_path] = content_hash(source.decode("utf-8", errors="replace"))

        report = IncrementalReport()
        for rel_path, actual_hash in current_files.items():
            stored_hash = existing_file_hashes.get(rel_path)
            if stored_hash is None:
                report.new_files.append(rel_path)
            elif stored_hash != actual_hash:
                report.changed_files.append(rel_path)
            else:
                report.unchanged_files.append(rel_path)
        report.deleted_files = sorted(set(existing_file_hashes) - set(current_files))

        builder = GraphBuilder(parse_cache=self.parse_cache)
        nodes, edges = builder.build(repo_root)
        self.last_parse_cache_hits = builder.cache_hits
        self.last_parse_cache_misses = builder.cache_misses

        touched_paths = set(report.new_files) | set(report.changed_files) | set(report.deleted_files)
        for rel_path in touched_paths:
            self.store.clear_file(rel_path)

        nodes_to_write = [n for n in nodes if n.file_path in touched_paths]
        self.store.upsert_nodes(nodes_to_write)
        # Edge inserts are idempotent (INSERT OR IGNORE) - reinserting the
        # full fresh edge set is a no-op for edges that already existed.
        self.store.insert_edges(edges)

        return report
