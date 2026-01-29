"""Shared types and helpers for language-specific tree-sitter extractors."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterator

from tree_sitter import Node as TSNode


@dataclass
class Symbol:
    """A class or function/method extracted from an AST, before it becomes a graph Node."""

    kind: str  # "CLASS" | "FUNCTION"
    name: str
    start_line: int
    end_line: int
    node: TSNode
    parent_name: str | None = None  # enclosing class name, if this is a method


@dataclass
class CallSite:
    """A call expression found inside some enclosing function symbol."""

    caller_name: str
    callee_name: str


@dataclass
class RawImport:
    """An import/include statement, as written in the source (unresolved)."""

    module: str


@dataclass
class FileExtraction:
    symbols: list[Symbol] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    imports: list[RawImport] = field(default_factory=list)


class LanguageExtractor:
    """Base class for one-per-language tree-sitter extraction logic."""

    language: str
    extensions: tuple[str, ...]

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        raise NotImplementedError


def walk(node: TSNode) -> Iterator[TSNode]:
    """Depth-first traversal of every node in the tree."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def node_text(node: TSNode, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def child_by_field(node: TSNode, field_name: str) -> TSNode | None:
    return node.child_by_field_name(field_name)


def innermost_identifier(node: TSNode | None, source: bytes) -> str | None:
    """Descend through pointer/reference declarator wrappers (C/C++) to find the
    identifier or field_identifier naming a declarator."""
    while node is not None:
        if node.type in ("identifier", "field_identifier", "type_identifier"):
            return node_text(node, source)
        inner = child_by_field(node, "declarator")
        if inner is None:
            return None
        node = inner
    return None


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_enclosing_function(node: TSNode, symbols: list[Symbol]) -> Symbol | None:
    """Smallest FUNCTION symbol whose byte range contains `node`, if any."""
    best: Symbol | None = None
    for s in symbols:
        if s.kind != "FUNCTION":
            continue
        if s.node.start_byte <= node.start_byte and node.end_byte <= s.node.end_byte:
            if best is None or (s.node.end_byte - s.node.start_byte) < (
                best.node.end_byte - best.node.start_byte
            ):
                best = s
    return best
