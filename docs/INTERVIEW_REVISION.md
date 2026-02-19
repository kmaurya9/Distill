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
- Measured on the real 8-language target corpus (2026-09-16), as stored:
  **33,129 nodes, 87,001 edges** (30,549 CONTAINS, 54,843 CALLS, 1,609
  IMPORTS). The `edges` PRIMARY KEY `(src_id, dst_id, kind)` deduplicates
  repeated call sites between the same two functions — the raw in-memory
  list is 119,406 long before that collapse.

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

## MMR re-ranking

**One-liner:** MMR (maximal marginal relevance) re-ranks the fused top-k by
iteratively picking `argmax(λ·relevance − (1−λ)·max_similarity_to_selected)`,
trading a little relevance for diversity so near-duplicate snippets don't
all occupy the final result.

**Key points:**
- Relevance scores are min-max normalized within the candidate pool before
  combining with cosine similarity (which lives in a different range).
- `λ=1` degenerates to plain top-k by relevance; `λ=0` degenerates to pure
  diversity (ignores relevance entirely) — `0.5` balances both.
- This is *exactly* the mechanism that reduces tokens sent to the agent
  without losing coverage: the fused top-k is often the same function found
  three ways (by name, by call site, by docstring) — MMR keeps one copy and
  spends the rest of the budget on genuinely different relevant code.
- Test (`tests/test_rerank.py`): a near-duplicate embedding is suppressed
  in favor of a lower-relevance-but-diverse one.

## MCP server

**One-liner:** `distill serve <repo>` indexes the repo in-memory and exposes
`search_code` / `get_symbol` / `get_context` as MCP tools over stdio — any
MCP-compatible agent (Claude Code, Cursor, a custom client) can call it
without any Distill-specific integration code.

**Key points:**
- Built on the official `mcp` Python SDK's `MCPServer` (this SDK major
  version renamed `FastMCP` → `MCPServer`; found via the actual
  `ModuleNotFoundError` migration message, not assumed from older docs).
- `search_code(query, k)` → fused + MMR-reranked snippets; `get_symbol(id)` →
  one symbol by node id; `get_context(file, line)` → smallest enclosing
  class/function for a file+line, falling back to the whole file.
- Proof it's real, not just "it runs": `tests/test_mcp_server.py` spawns
  `distill serve` as a subprocess and drives it with the official MCP
  **client** SDK over stdio (the same transport a real agent uses) — list
  tools, call `search_code`, get back real ranked results with content.

**Likely Q&A:**
- *Why stdio instead of SSE/HTTP?* Stdio is what a local coding agent
  (Claude Code, Cursor) spawns as a subprocess — no server process or port to
  manage, matches how `pip install distill-mcp && distill serve <repo>` is
  meant to be used.
- *Does the index update if the repo changes while the server is running?*
  Not yet — the server builds the index once at startup (though startup
  itself now reuses the on-disk parse/embedding cache from any prior
  `distill index` run — see the Incremental indexing / caching card). Live
  re-indexing of a *running* server is a natural next step, not yet built.

## Incremental indexing / caching

**One-liner:** re-running `distill index` (or starting `distill serve`)
against a repo that's already been indexed only re-parses and re-embeds
files whose content actually changed — everything else is read from the
`.distill/graph.db` cache untouched.

**Key points:**
- Change detection is **content-hash based, not mtime-based**: each file's
  current hash is compared to the hash stored on its FILE node. Robust to
  `touch`, checkouts, and clock skew (verified — `touch`ing a file with
  unchanged content correctly reports 0 changed files).
- Content-addressed caching (`distill/indexing/cache.py`) has two caches,
  both keyed by `hash(content)`, not by path: `ParseCache` (skip re-running
  tree-sitter + symbol extraction) and `EmbeddingCache` (skip re-running the
  embedding model). Identical content at a *different* path (a vendored
  copy, a duplicated function) is a cache hit either way.
- A full in-memory graph pass still runs on every re-index — CALLS/IMPORTS
  resolution is inherently repo-wide — but only *touched* files' nodes get
  written back to the store; untouched files' rows are never re-issued.
- Measured on the real flask corpus: cold index ~0.2s; re-running against
  the same unchanged repo: **0.0s wall / all 83 files reported unchanged**.

**Likely Q&A:**
- *Why content hash instead of mtime/git-diff, like the build plan
  suggested?* Content hash is what the plan's schema already stores per
  node (`content_hash` column, meant for caching) — reusing it for change
  detection avoids a second detection mechanism and is correct regardless
  of filesystem timestamp resolution or whether the repo is even a git repo.
- *What's the actual proof "only that file's nodes are touched," not just
  "the count looks right"?* `tests/test_incremental.py` fetches the
  unrelated file's node object before and after modifying a different file,
  and asserts it's byte-for-byte identical — plus asserts the parse cache
  reports 0 misses for the untouched file.

## Retrieval-quality evaluation (measured)

**One-liner:** 20 hand-verified queries (found by grepping the real target
corpus, reading the actual implementation, then looking up its real node id
— not guessed) show the full fused+MMR pipeline's recall@1 (0.70) more than
doubling BM25-alone (0.30) or embeddings-alone (0.40).

**Key points:**
- Full results (`docs/BENCHMARKS.md`): BM25-only MRR 0.474, embeddings-only
  MRR 0.545, full pipeline MRR **0.739**.
- Deliberately included hard/near-duplicate cases (e.g. `get_cookie_domain`
  vs. `get_cookie_httponly` — five very similarly-worded methods in the same
  class) to stress-test whether fusion earns its keep on genuinely ambiguous
  queries, not just easy ones.
- Capped at 20 queries instead of the build plan's 30–50 — an explicit,
  documented scope cut (playbook's fallback ladder), not a silent shortcut:
  hand-labeling (verifying each answer is actually correct) is the one task
  here that can't be sped up by tooling.

**Likely Q&A:**
- *How do you know the labels are actually correct, not just plausible
  function names?* Each one was read in full before being added — e.g. the
  `logerror` label was only added after confirming it does exactly "log to
  stderr unless `env === 'test'`," not assumed from the name.
- *Why report recall@1 specifically as the headline number?* It's the
  strictest, most interview-relevant metric — "does the very first result
  answer the question" is what determines whether an agent needs a second
  round-trip.

## Token-reduction result (measured)

**One-liner:** measured (not assumed) token counts, via `tiktoken`
`cl100k_base`, show a 55% mean / 76% aggregate reduction versus reading the
whole file containing the answer — with an honestly-reported negative
outlier case explained, not hidden.

**Key points:**
- Naive baseline = whole file containing the answer; Distill = `search_code`
  MMR top-5. Aggregate: 90,450 → 21,700 tokens (76.0% reduction).
- 3 of 20 queries show a *negative* reduction — all are cases where the
  naive file is already small (554–1,388 tokens) and a fixed `k=5` overshoots
  it by pulling in snippets from other, larger files.
- The résumé's placeholder "40–90%" isn't exactly this repo's measured
  range — the honest number to say out loud is **55% mean / 76% aggregate**,
  with the caveat above, per the build plan's explicit instruction to report
  what's measured rather than force-fit the placeholder.

**Likely Q&A:**
- *Why does reduction vary so much per query (-82% to 93%)?* Reduction scales
  with how large/numerous the naive alternative is. Serving a static file
  required reading a 13,737-token file naively vs. 954 tokens via Distill
  (93.1%) — a large file benefits enormously. A single 554-token logging
  module needs no retrieval at all; forcing `k=5` there can lose.
- *Why `k=5` and not tune it per query?* Fixed `k` matches how an agent
  would actually call `search_code` in practice (one budget, not a
  per-query oracle) — tuning `k` per query to always win would be
  overfitting the benchmark, not measuring it honestly.
