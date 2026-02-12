import time
from pathlib import Path

import click

from distill import __version__
from distill.indexing.cache import ParseCache
from distill.indexing.incremental import IncrementalIndexer
from distill.store.graph_store import GraphStore

@click.group()
@click.version_option(__version__)
def main():
    """Distill: code-retrieval engine and MCP server for coding agents."""


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False))
@click.option("--db", "db_path", type=click.Path(), default=None, help="Graph DB path (default: <repo>/.distill/graph.db)")
def index(repo_path: str, db_path: str | None):
    """Index a repository into the code graph + retrieval indices.

    Incremental: re-running against an existing --db only re-parses and
    re-writes new/changed/deleted files; unchanged files are untouched.
    """
    repo = Path(repo_path).resolve()
    db = Path(db_path) if db_path else repo / ".distill" / "graph.db"
    db.parent.mkdir(parents=True, exist_ok=True)

    store = GraphStore(db)
    parse_cache = ParseCache(store)
    indexer = IncrementalIndexer(store, parse_cache=parse_cache)

    start = time.time()
    report = indexer.reindex(repo)
    elapsed = time.time() - start

    click.echo(f"Indexed {repo} in {elapsed:.1f}s")
    click.echo(f"  new files: {len(report.new_files)}")
    click.echo(f"  changed files: {len(report.changed_files)}")
    click.echo(f"  unchanged files: {len(report.unchanged_files)}")
    click.echo(f"  deleted files: {len(report.deleted_files)}")
    click.echo(f"  nodes: {store.node_count()}")
    click.echo(f"  edges: {store.edge_count()}")
    click.echo(f"  graph db: {db}")
    store.close()


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False))
def serve(repo_path: str):
    """Index a repo and start the Distill MCP server (stdio transport)."""
    from distill.server.mcp_server import build_server

    server = build_server(Path(repo_path).resolve())
    server.run()


if __name__ == "__main__":
    main()
