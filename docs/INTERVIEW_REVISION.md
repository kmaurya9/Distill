# Interview Revision Cards

One card per phase. Every card matches the code that exists, including real
measured numbers — not the résumé's placeholder numbers.

## Architecture overview

**One-liner:** Distill is an MCP server that indexes a repo into a code
graph, retrieves with BM25 + dense embeddings fused by RRF, then re-ranks
with MMR to hand an agent a small, relevant, non-redundant context window.

**Key points:**
- Indexing: tree-sitter → AST → graph (nodes = file/class/function, edges =
  calls/imports/contains) → SQLite.
- Retrieval: BM25 (lexical) + dense embeddings (semantic), fused with RRF,
  weighted by a PageRank prior, then MMR removes near-duplicates.
- Exposed to any MCP-compatible agent via `search_code` / `get_symbol` /
  `get_context` tools.

**Likely Q&A:**
- *Why not just embeddings?* Embeddings miss exact identifier/keyword matches
  that BM25 catches, and vice versa for paraphrases — fusing both is standard
  practice for retrieval quality.
- *Why a graph instead of a flat chunk index?* Code isn't a bag of text —
  call/import structure lets PageRank prioritize widely-used utilities over
  dead code, and lets `get_context` walk from a snippet to its callers.

## tree-sitter / program analysis

**One-liner:** One extractor module per language walks that language's
tree-sitter AST to pull out classes/functions (nodes) and call/import sites
(edges), verified against real sample files per language.

**Key points:**
- 8 languages: Python, JavaScript, TypeScript, Java, Go, Rust, C, C++, via
  `tree-sitter-language-pack` (one grammar dependency, not 8).
- Node type names differ per grammar (`function_definition` in Python vs.
  `function_declaration`/`method_definition` in JS) — determined empirically
  by dumping real ASTs, not guessed from memory.
- CALLS resolution: name-based, same-file preferred, else a global name
  index within the same repo — not full type resolution (documented
  limitation, see `docs/DECISIONS.md`).
- IMPORTS resolution: written module/include string normalized several ways
  (dotted → path, relative-to-importer, `::` → path) and matched against an
  index of indexed file paths.

**Likely Q&A:**
- *How do you know the parser is correct, not just that it runs?* Golden-file
  tests per language (`tests/test_parsers.py`) assert the exact expected
  symbol set, CALLS edges, and imports against a hand-written sample file.
- *What's the biggest limitation?* No type checker — a call to a common name
  can match the wrong same-named function if there are multiple candidates
  in scope. Acceptable for a lightweight, dependency-free static analyzer.

## Code graph

**One-liner:** Files, classes, and functions become graph nodes; calls,
imports, and containment become edges, persisted in SQLite so retrieval and
re-indexing don't need to re-parse.

**Key points:**
- Schema: `nodes(id, kind, name, file_path, language, start_line, end_line,
  docstring, content_hash)`, `edges(src_id, dst_id, kind)`,
  `cache(content_hash, parsed_json, embedding)`.
- Node id = `{file_path}::{qualified_name}::{start_line}` — stable across
  re-runs as long as the symbol doesn't move/rename.
- Measured on the real 8-language target corpus (2026-09-16): **33,129
  nodes, 119,406 edges** (30,549 CONTAINS, 87,248 CALLS, 1,609 IMPORTS).

**Likely Q&A:**
- *Why SQLite instead of a graph database?* The graph is a few hundred
  thousand nodes/edges at most for a real repo — SQLite with indexed
  `file_path`/`src_id`/`dst_id` columns is simpler to ship (`pip install
  distill-mcp` stays self-contained) and fast enough; `networkx` handles
  in-memory graph algorithms like PageRank on top of it.
- *How did you actually get 33K nodes?* Combined 8 real open-source repos
  (one per target language — flask, express, zod, gson, gin, ripgrep, redis,
  json), indexed each independently so name resolution doesn't leak across
  repos, then merged with namespaced ids. See `docs/BENCHMARKS.md`.
