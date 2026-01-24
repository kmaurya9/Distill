# Distill

An open-source MCP server and code-retrieval engine for coding agents.

Point Distill at a repo; it parses the code into a graph (tree-sitter AST across
8 languages), indexes it with dense embeddings + BM25, ranks nodes with
PageRank, fuses the rankings with reciprocal-rank fusion (RRF), then re-ranks
with MMR to hand an agent a small, non-redundant, highly relevant set of code
snippets — instead of dumping whole files into the prompt.

See `Distill-Build-Plan.md` for the architecture, data model, and the
claim-to-proof table this project is built against.

## Install

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Usage

```bash
distill index /path/to/target/repo
distill serve   # starts the MCP server (stdio)
```

Add Distill as an MCP server in an MCP-compatible client (e.g. Claude Code) and
call `search_code("where do we validate auth tokens?")`.

## Development

```bash
pytest
```

See `docs/DECISIONS.md` for design decisions and `docs/BENCHMARKS.md` for
measured retrieval-quality and token-reduction numbers.
