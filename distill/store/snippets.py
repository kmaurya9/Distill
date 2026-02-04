"""Reads a graph node's source text back off disk, on demand.

Nodes store `file_path` + `start_line`/`end_line`, not the text itself — this
keeps the graph store small and matches the MCP `get_context(file, line)`
tool's semantics (read from the live repo, not a frozen copy).
"""

from __future__ import annotations

from pathlib import Path

from distill.indexing.graph_builder import GraphNode


class SnippetReader:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)
        self._file_lines_cache: dict[str, list[str]] = {}

    def _lines(self, file_path: str) -> list[str]:
        if file_path not in self._file_lines_cache:
            text = (self.repo_root / file_path).read_text(encoding="utf-8", errors="replace")
            self._file_lines_cache[file_path] = text.splitlines()
        return self._file_lines_cache[file_path]

    def read(self, node: GraphNode) -> str:
        lines = self._lines(node.file_path)
        return "\n".join(lines[node.start_line - 1 : node.end_line])
