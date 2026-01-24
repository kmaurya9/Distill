import click

from distill import __version__


@click.group()
@click.version_option(__version__)
def main():
    """Distill: code-retrieval engine and MCP server for coding agents."""


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False))
def index(repo_path: str):
    """Index a repository into the code graph + retrieval indices."""
    click.echo(f"Indexing {repo_path} ... (not yet implemented)")


@main.command()
def serve():
    """Start the Distill MCP server (stdio transport)."""
    click.echo("Starting Distill MCP server ... (not yet implemented)")


if __name__ == "__main__":
    main()
