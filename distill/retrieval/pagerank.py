from __future__ import annotations

import networkx as nx

from distill.indexing.graph_builder import GraphEdge, GraphNode

STRUCTURAL_EDGE_KINDS = ("CALLS", "IMPORTS")


def compute_pagerank(nodes: list[GraphNode], edges: list[GraphEdge]) -> dict[str, float]:
    """PageRank over the call/import graph: a node called/imported from many
    places scores higher than one nobody references."""
    if not nodes:
        return {}

    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(node.id)
    for edge in edges:
        if edge.kind in STRUCTURAL_EDGE_KINDS:
            graph.add_edge(edge.src_id, edge.dst_id)

    if graph.number_of_edges() == 0:
        uniform = 1.0 / len(nodes)
        return {node.id: uniform for node in nodes}

    return nx.pagerank(graph)
