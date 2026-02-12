from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tree_sitter_language_pack import get_parser

from distill.indexing.imports import ImportIndex
from distill.indexing.parsers.base import FileExtraction, content_hash
from distill.indexing.parsers.registry import get_extractor

if TYPE_CHECKING:
    # Avoids a cycle: graph_builder <- cache <- graph_store <- graph_builder.
    from distill.indexing.cache import ParseCache

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "target",
    "build", "dist", "vendor", ".idea", ".vscode", ".pytest_cache", "egg-info",
}


@dataclass
class GraphNode:
    id: str
    kind: str  # FILE | CLASS | FUNCTION
    name: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    docstring: str | None
    content_hash: str


@dataclass
class GraphEdge:
    src_id: str
    dst_id: str
    kind: str  # CALLS | IMPORTS | CONTAINS


@dataclass
class _ParsedFile:
    rel_path: str
    language: str
    extraction: FileExtraction
    file_node_id: str
    local_function_ids: dict[str, str]


def iter_source_files(repo_root: Path):
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            path = Path(dirpath) / filename
            if get_extractor(path.suffix) is not None:
                yield path


class GraphBuilder:
    """Walks a repo, parses every recognized source file with the matching
    tree-sitter extractor, and builds the code graph (nodes + edges)."""

    def __init__(self, parse_cache: "ParseCache | None" = None) -> None:
        self.parse_cache = parse_cache
        self.cache_hits = 0
        self.cache_misses = 0

    def build(self, repo_root: str | Path) -> tuple[list[GraphNode], list[GraphEdge]]:
        repo_root = Path(repo_root).resolve()
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        parsed_files: list[_ParsedFile] = []
        rel_paths: list[str] = []
        name_index: dict[str, list[str]] = defaultdict(list)  # bare name -> node ids (global)

        for path in iter_source_files(repo_root):
            rel_path = path.relative_to(repo_root).as_posix()
            extractor = get_extractor(path.suffix)
            if extractor is None:
                continue
            try:
                source = path.read_bytes()
            except OSError:
                continue

            file_hash = content_hash(source.decode("utf-8", errors="replace"))
            extraction = self.parse_cache.get(file_hash) if self.parse_cache else None
            if extraction is not None:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
                parser = get_parser(extractor.language)
                tree = parser.parse(source)
                extraction = extractor.extract(source, tree.root_node)
                if self.parse_cache:
                    self.parse_cache.put(file_hash, extraction)

            file_node_id = rel_path
            num_lines = source.count(b"\n") + 1
            nodes.append(
                GraphNode(
                    id=file_node_id,
                    kind="FILE",
                    name=path.name,
                    file_path=rel_path,
                    language=extractor.language,
                    start_line=1,
                    end_line=num_lines,
                    docstring=None,
                    content_hash=file_hash,
                )
            )

            class_node_id_by_name: dict[str, str] = {}
            for symbol in extraction.symbols:
                if symbol.kind != "CLASS":
                    continue
                qualified = symbol.name
                node_id = f"{rel_path}::{qualified}::{symbol.start_line}"
                class_node_id_by_name[symbol.name] = node_id
                text = source[symbol.start_byte : symbol.end_byte].decode(
                    "utf-8", errors="replace"
                )
                nodes.append(
                    GraphNode(
                        id=node_id,
                        kind="CLASS",
                        name=symbol.name,
                        file_path=rel_path,
                        language=extractor.language,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        docstring=None,
                        content_hash=content_hash(text),
                    )
                )
                edges.append(GraphEdge(src_id=file_node_id, dst_id=node_id, kind="CONTAINS"))
                name_index[symbol.name].append(node_id)

            function_node_id_by_name: dict[str, str] = {}
            for symbol in extraction.symbols:
                if symbol.kind != "FUNCTION":
                    continue
                qualified = f"{symbol.parent_name}.{symbol.name}" if symbol.parent_name else symbol.name
                node_id = f"{rel_path}::{qualified}::{symbol.start_line}"
                text = source[symbol.start_byte : symbol.end_byte].decode(
                    "utf-8", errors="replace"
                )
                nodes.append(
                    GraphNode(
                        id=node_id,
                        kind="FUNCTION",
                        name=symbol.name,
                        file_path=rel_path,
                        language=extractor.language,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        docstring=None,
                        content_hash=content_hash(text),
                    )
                )
                parent_id = (
                    class_node_id_by_name.get(symbol.parent_name) if symbol.parent_name else None
                )
                edges.append(
                    GraphEdge(
                        src_id=parent_id or file_node_id, dst_id=node_id, kind="CONTAINS"
                    )
                )
                name_index[symbol.name].append(node_id)
                function_node_id_by_name.setdefault(symbol.name, node_id)

            parsed_files.append(
                _ParsedFile(
                    rel_path=rel_path,
                    language=extractor.language,
                    extraction=extraction,
                    file_node_id=file_node_id,
                    local_function_ids=function_node_id_by_name,
                )
            )
            rel_paths.append(rel_path)

        # Resolve CALLS: prefer same-file match, else any global match (first, deterministic).
        for pf in parsed_files:
            local_ids = pf.local_function_ids
            for call in pf.extraction.calls:
                caller_id = local_ids.get(call.caller_name)
                if caller_id is None:
                    continue
                callee_id = local_ids.get(call.callee_name)
                if callee_id is None:
                    matches = name_index.get(call.callee_name)
                    callee_id = matches[0] if matches else None
                if callee_id is None or callee_id == caller_id:
                    continue
                edges.append(GraphEdge(src_id=caller_id, dst_id=callee_id, kind="CALLS"))

        # Resolve IMPORTS: file -> file, best-effort path resolution.
        import_index = ImportIndex(rel_paths)
        seen_import_edges: set[tuple[str, str]] = set()
        for pf in parsed_files:
            for raw_import in pf.extraction.imports:
                target = import_index.resolve(raw_import.module, pf.rel_path)
                if target is None or target == pf.rel_path:
                    continue
                key = (pf.file_node_id, target)
                if key in seen_import_edges:
                    continue
                seen_import_edges.add(key)
                edges.append(GraphEdge(src_id=pf.file_node_id, dst_id=target, kind="IMPORTS"))

        return nodes, edges
