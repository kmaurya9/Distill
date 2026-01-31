"""Combine several independently-indexed repos into one graph.

Used to build the target-corpus benchmark graph (docs/BENCHMARKS.md): each
repo is indexed on its own (so name-based CALLS/IMPORTS resolution never
crosses repo boundaries), then node/edge ids are namespaced by repo name so
they can be merged into a single store without collisions.
"""

from __future__ import annotations

from pathlib import Path

from distill.indexing.graph_builder import GraphBuilder, GraphEdge, GraphNode


def build_multi_repo(repo_paths: list[Path]) -> tuple[list[GraphNode], list[GraphEdge]]:
    all_nodes: list[GraphNode] = []
    all_edges: list[GraphEdge] = []

    for repo_path in repo_paths:
        prefix = repo_path.name
        nodes, edges = GraphBuilder().build(repo_path)
        for n in nodes:
            n.id = f"{prefix}/{n.id}"
            n.file_path = f"{prefix}/{n.file_path}"
        for e in edges:
            e.src_id = f"{prefix}/{e.src_id}"
            e.dst_id = f"{prefix}/{e.dst_id}"
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    return all_nodes, all_edges
