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

## BM25 vs. embeddings

**One-liner:** BM25 is exact-term lexical scoring (great for identifiers,
error strings, exact keyword matches); embeddings capture semantic similarity
(great for paraphrased natural-language queries) — fusing both covers what
either misses alone.

**Key points:**
- BM25 via `bm25s`; dense via a local `sentence-transformers` model
  (`all-MiniLM-L6-v2`), no API key required.
- Corpus and query **must** share one `Tokenizer` instance/vocab in `bm25s` —
  tokenizing them separately silently builds mismatched vocabularies and
  zeroes every score on a small corpus (real bug hit and fixed here; see
  `docs/DECISIONS.md`).
- Retrieval candidates are CLASS/FUNCTION nodes only (not FILE nodes) — a
  whole file is a poor "snippet" and, for small files, a near-duplicate of
  the one symbol it contains.

**Likely Q&A:**
- *Why didn't the BM25 unit test catch the tokenizer bug?* It used one
  `BM25Index.build()` + `.search()` call, which happened to route through the
  same (buggy) code path consistently for that specific corpus size. The
  Phase 2 end-to-end pipeline integration test — a real query against a real
  small repo — is what surfaced it. Lesson: per-stage unit tests and one
  integration test both matter; they catch different classes of bugs.
- *Why cosine similarity via FAISS `IndexFlatIP` instead of L2 distance?*
  Embeddings are L2-normalized at encode time, so inner product equals cosine
  similarity — flat (exact, brute-force) search is fine at this node count;
  swappable for an ANN index (e.g. `IndexIVFFlat`) if the corpus grew large
  enough that exact search became the bottleneck.

## Reciprocal-rank fusion (RRF)

**One-liner:** RRF combines multiple ranked lists into one by scoring each
item `1/(k+rank)` per list it appears in and summing — no need to normalize
or compare raw BM25 vs. cosine scores, which live on incomparable scales.

**Key points:**
- Formula verified against a hand-computed toy case in
  `tests/test_fusion.py` (`k=1`, two 3-item lists, exact expected scores).
- Rank-only: a document present but scored 0 relevance in a list still gets
  the same rank-based credit as one scored 0.01 — a known RRF blind spot,
  most visible with very small candidate sets (a couple of items can tie
  perfectly and cancel out a real signal from the other list).
- PageRank is layered on top as an additive prior
  (`apply_pagerank_prior`), not folded into the RRF sum itself — keeps the
  fusion formula itself exactly the standard, textbook one.

**Likely Q&A:**
- *Why RRF instead of a weighted sum of raw scores?* BM25 scores and cosine
  similarities aren't on comparable scales (BM25 is unbounded, cosine is
  [-1,1]) — RRF sidesteps needing to normalize them by only using rank
  position, which is standard practice for fusing heterogeneous rankers.
- *What's `k` for?* A smoothing constant — larger `k` flattens the
  difference between e.g. rank 1 and rank 2 (`1/61` vs `1/62` is a tiny gap);
  smaller `k` makes top ranks dominate much more sharply.
