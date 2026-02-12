from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from distill import __version__
from distill.indexing.cache import EmbeddingCache, ParseCache
from distill.indexing.graph_builder import GraphNode
from distill.indexing.incremental import IncrementalIndexer
from distill.retrieval.pipeline import RetrievalIndex
from distill.store.graph_store import GraphStore
from distill.store.snippets import SnippetReader


def _node_payload(node: GraphNode, content: str, score: float | None = None) -> dict:
    payload = {
        "id": node.id,
        "name": node.name,
        "kind": node.kind,
        "file_path": node.file_path,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "content": content,
    }
    if score is not None:
        payload["score"] = score
    return payload


def build_server(repo_path: Path, db_path: Path | None = None) -> MCPServer:
    """Index `repo_path` (incrementally, reusing any existing `.distill/graph.db`
    parse/embedding cache) and return an MCPServer exposing search_code /
    get_symbol / get_context over that repo."""
    server = MCPServer(
        name="distill",
        version=__version__,
        instructions=(
            "Code-retrieval engine for coding agents. Call search_code with a "
            "natural-language or keyword query to get a small, non-redundant "
            "set of relevant code snippets instead of reading whole files."
        ),
    )

    db_path = db_path or repo_path / ".distill" / "graph.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = GraphStore(db_path)
    parse_cache = ParseCache(store)
    IncrementalIndexer(store, parse_cache=parse_cache).reindex(repo_path)

    nodes = store.all_nodes()
    edges = store.all_edges()
    nodes_by_id = {n.id: n for n in nodes}
    reader = SnippetReader(repo_path)

    retrieval_index = RetrievalIndex()
    embedding_cache = EmbeddingCache(store, dim=retrieval_index.embedding_model.dim)
    retrieval_index.build(nodes, edges, repo_path, embedding_cache=embedding_cache)

    @server.tool()
    def search_code(query: str, k: int = 10) -> list[dict]:
        """Search the indexed repo for code relevant to a natural-language or
        keyword query. Returns a small, non-redundant, ranked list of
        snippets (fused BM25 + dense retrieval, MMR re-ranked)."""
        results = retrieval_index.search(query, k=k)
        return [
            _node_payload(nodes_by_id[node_id], reader.read(nodes_by_id[node_id]), score)
            for node_id, score in results
            if node_id in nodes_by_id
        ]

    @server.tool()
    def get_symbol(node_id: str) -> dict | None:
        """Fetch a specific class or function by its node id (as returned by
        search_code)."""
        node = nodes_by_id.get(node_id)
        if node is None:
            return None
        return _node_payload(node, reader.read(node))

    @server.tool()
    def get_context(file_path: str, line: int) -> dict | None:
        """Fetch the smallest class/function enclosing a given file + line
        number, falling back to the whole file if no symbol contains it."""
        enclosing = [
            n
            for n in nodes
            if n.file_path == file_path
            and n.kind in ("CLASS", "FUNCTION")
            and n.start_line <= line <= n.end_line
        ]
        if enclosing:
            best = min(enclosing, key=lambda n: n.end_line - n.start_line)
            return _node_payload(best, reader.read(best))

        file_node = next((n for n in nodes if n.file_path == file_path and n.kind == "FILE"), None)
        if file_node is None:
            return None
        return _node_payload(file_node, reader.read(file_node))

    return server
