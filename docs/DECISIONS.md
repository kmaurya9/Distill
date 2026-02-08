# Decisions

One entry per non-obvious choice, with the why.

## 2026-09-16 — Local embeddings (sentence-transformers) instead of OpenAI

Avoids requiring a paid API key for development and keeps `pip install
distill-mcp` self-contained, per the build plan's "pluggable embeddings"
requirement. OpenAI `text-embedding-3-small` remains a swappable option later.

## 2026-09-16 — Target corpus: 8 repos, one per tree-sitter language

Combining single-language repos (rather than one polyglot monorepo) makes the
per-language node/edge counts easy to attribute and reproduce:

| Language | Repo |
|---|---|
| Python | pallets/flask |
| JavaScript | expressjs/express |
| TypeScript | colinhacks/zod |
| Java | google/gson |
| Go | gin-gonic/gin |
| Rust | BurntSushi/ripgrep |
| C | redis/redis |
| C++ | nlohmann/json |

Cloned shallow (`--depth 1`) into `corpora/` (gitignored — not part of the
published package). Actual node/edge counts from indexing these are reported
in `docs/BENCHMARKS.md`, not assumed.

## 2026-09-16 — Python 3.12 for the dev venv

System default is 3.14, but tree-sitter-language-pack / faiss-cpu wheel
availability lags newest CPython releases. `pyproject.toml` still declares
`requires-python = ">=3.11"` for the published package; 3.12 is just the
pinned dev environment.

## 2026-09-16 — `tree-sitter-language-pack` over per-language `tree-sitter-<lang>` packages

One dependency providing prebuilt grammars for all 8 target languages instead
of managing 8 separate grammar packages and their ABI-version compatibility
with the `tree-sitter` core package individually.

## 2026-09-16 — Name-based (not type-resolved) CALLS/IMPORTS resolution

Building a real type checker per language is out of scope. CALLS edges
resolve a call site's callee name first against functions in the same file,
then against a global name index; ties pick the first match deterministically.
IMPORTS edges resolve the written module/include string against an index of
every indexed file's path (several normalized forms: dotted → path, relative-
to-importer, `::` → path). External/stdlib imports that don't correspond to
an indexed file simply don't produce an edge — correct behavior, not a bug.

This is honest best-effort program analysis, not full call-graph precision.
Documented so the PageRank/graph claims aren't overstated.

## 2026-09-16 — Multi-repo target corpus indexed per-repo, then merged with namespaced ids

Indexing all 8 corpus repos in one `GraphBuilder.build()` call (by pointing
it at their common parent directory) let the global name-index CALLS
resolution match same-named functions **across unrelated repos** (e.g. a
`main` in `redis` resolving to a `main` in `gin`) — inflated edge count from
a real run of 127,836 down to the correct 119,406 once fixed. Fix
(`distill.indexing.multi_repo.build_multi_repo`): index each repo
independently (so name resolution stays scoped to that repo, which is also
what happens in normal single-repo usage via `distill index`), then merge
node/edge lists with an `f"{repo_name}/{id}"` prefix to avoid id collisions.
This is a benchmark-corpus-only concern — normal `distill index <repo>`
usage is unaffected since it only ever sees one repo per call.

## 2026-09-16 — `bm25s` requires a shared `Tokenizer` for corpus and query

`bm25s.tokenize(texts)` called once for the corpus and again for a query
builds two **independent** word→id vocabularies. With a small corpus,
tokenizer output looks fine in isolation but every query then scores 0 —
the query's token ids don't correspond to the corpus's ids at all, so
`retrieve()` compares apples to oranges. Caught by the Phase 2 end-to-end
pipeline integration test (`tests/test_pipeline.py`), not by the isolated
unit test (`tests/test_bm25_index.py`), which happened not to expose it —
a reminder that unit tests per stage don't replace an integration test.

Fix: `distill.retrieval.bm25_index.BM25Index` owns one `bm25s.tokenization.
Tokenizer` instance; the corpus is indexed with `update_vocab=True`, queries
with `update_vocab=False` so unseen query words are dropped (correct — they
can't match anything in the corpus) rather than silently reassigned new ids.

## 2026-09-16 — `mcp` SDK v2 renamed `FastMCP` to `MCPServer`

`pyproject.toml` pins `mcp>=1.2.0` (loose), which resolved to `2.2.0` — a
major version where `mcp.server.fastmcp.FastMCP` was renamed to
`mcp.server.mcpserver.MCPServer` (discovered from the real
`ModuleNotFoundError` migration message, not assumed from docs written for
v1). API is otherwise equivalent: `.tool()` decorator, `.run()` /
`.run_stdio_async()`.

## 2026-09-16 — Retrieval candidates are CLASS/FUNCTION nodes, not FILE nodes

FILE nodes are part of the graph (for PageRank's IMPORTS edges and
`get_context`), but including them as BM25/embedding search candidates makes
small files near-duplicates of the one symbol they contain, which pollutes
ranking with a redundant near-tie. `RetrievalIndex` computes PageRank over the
full graph but only builds the BM25/vector indices over CLASS/FUNCTION nodes.
