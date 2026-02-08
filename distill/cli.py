import time
from pathlib import Path

import click

from distill import __version__
from distill.indexing.graph_builder import GraphBuilder
from distill.store.graph_store import GraphStore

@click.group()
@click.version_option(__version__)
def main():
    """Distill: code-retrieval engine and MCP server for coding agents."""


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False))
@click.option("--db", "db_path", type=click.Path(), default=None, help="Graph DB path (default: <repo>/.distill/graph.db)")
def index(repo_path: str, db_path: str | None):
    """Index a repository into the code graph + retrieval indices."""
    repo = Path(repo_path).resolve()
    db = Path(db_path) if db_path else repo / ".distill" / "graph.db"
    db.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()
    nodes, edges = GraphBuilder().build(repo)
    store = GraphStore(db)
    store.clear()
    store.upsert_nodes(nodes)
    store.insert_edges(edges)
    store.close()
    elapsed = time.time() - start

    click.echo(f"Indexed {repo} in {elapsed:.1f}s")
    click.echo(f"  nodes: {len(nodes)}")
    click.echo(f"  edges: {len(edges)}")
    click.echo(f"  graph db: {db}")


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False))
def serve(repo_path: str):
    """Index a repo and start the Distill MCP server (stdio transport)."""
    from distill.server.mcp_server import build_server

    server = build_server(Path(repo_path).resolve())
    server.run()


if __name__ == "__main__":
    main()
