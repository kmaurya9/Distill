# Benchmarks

Real, measured numbers only. Nothing here is assumed or rounded up to match
the résumé placeholder — the résumé wording gets adjusted to match what's
measured here, not the other way around.

## Target corpus graph size (claim #8)

**Corpus:** 8 repos, one per tree-sitter target language, cloned shallow
(`git clone --depth 1`) on 2026-09-16 (see `docs/DECISIONS.md` for the list
and rationale).

**Method:** each repo indexed independently with `GraphBuilder` (so CALLS/
IMPORTS resolution never crosses repo boundaries), then merged into one graph
with repo-namespaced ids (`distill.indexing.multi_repo.build_multi_repo`).
Reproduce with:

```bash
python3 -c "
from pathlib import Path
from distill.indexing.multi_repo import build_multi_repo
from distill.store.graph_store import GraphStore
repos = ['flask','express','zod','gson','gin','ripgrep','redis','json']
nodes, edges = build_multi_repo([Path('corpora')/r for r in repos])
store = GraphStore('graph.db'); store.clear()
store.upsert_nodes(nodes); store.insert_edges(edges); store.close()
print(len(nodes), len(edges))
"
```

**Result (measured 2026-09-16, as stored in the graph DB):**

| Metric | Count |
|---|---|
| Total nodes | **33,129** |
| Total edges | **87,001** |
| — CONTAINS | 30,549 |
| — CALLS | 54,843 |
| — IMPORTS | 1,609 |
| FILE nodes | 2,580 |
| CLASS nodes | 3,672 |
| FUNCTION nodes | 26,877 |

Per-repo file counts by language: python 138, javascript 147, typescript 511,
java 264, go 99, rust 110, c 806, cpp 505.

Crosses the 12K+ node claim by a wide margin (33,129 nodes); even the largest
single repo alone (redis, 13,114 nodes) exceeds it.

**Note on the edge count:** `GraphBuilder.build()` returns a raw edge list
that can contain duplicate `(src_id, dst_id, kind)` triples — e.g. function
A calling function B three times in its body produces three `CallSite`
records, hence three list entries for the same logical edge. The `edges`
table's `PRIMARY KEY (src_id, dst_id, kind)` collapses these on insert (the
correct semantics — PageRank and the graph care whether an edge *exists*,
not how many call sites produced it). The raw list is 119,406 long; **87,001**
is the real, deduplicated number as it exists in the graph DB and is what's
reported here. Caught by re-deriving this number through an actual
`GraphStore` instead of trusting the in-memory list length.

**Known limitation:** CALLS/IMPORTS resolution is name-and-path based, not
type-resolved — a call to a common name (e.g. `init`) can match the wrong
same-named function within one repo if there are multiple candidates. This is
a documented tradeoff of lightweight static analysis without a type checker
per language (see `docs/DECISIONS.md`).

## Regression test suite (claim #14)

**Real count (measured 2026-09-16):** `pytest` collects **43 tests** — not
padded to the résumé placeholder's 157. Breakdown: 8 golden-file parser
tests (one per language), graph builder (4), graph store (3), multi-repo
namespacing (1), incremental indexing (3), content-addressed caching (4),
BM25 (2), embeddings (1), PageRank (2), RRF/fusion (3), MMR (2), pipeline
integration (2, including the embedding-cache-reuse case), snippets (1), a
real MCP client-to-server integration test plus 2 edge-case MCP tests (3),
and CLI (4).

Reproduce: `pytest tests/` → `43 passed`.

**Why 43 and not 157:** the build plan's own instructions are explicit that
the test count is "whatever pytest actually collects... don't pad to hit a
number." This suite covers every claim in the claim-to-proof table with a
real, non-trivial test (several caught actual bugs during development — see
`docs/DECISIONS.md`: the bm25s vocab-mismatch bug, the cross-repo
name-collision bug, and the empty-corpus BM25 crash were all found this way,
not by inspection).

## Retrieval-quality evaluation (claim #14)

**Labeled set:** 20 hand-verified queries (`eval/dataset/queries.json`)
against a flask + express eval corpus (1,973 nodes, 3,741 edges). Capped at
20 rather than the build plan's 30–50 — per the playbook's fallback ladder
("cap the eval set smaller ... still real numbers, just a smaller sample,
say so honestly") — because hand-labeling is the one genuinely
un-acceleratable task here: each label required grepping the real source for
a plausible answer, then **reading the actual implementation** to confirm it
answers the query, then looking up its real node id in the indexed graph.
Not fabricated or guessed from function names alone.

**Method:** `eval/run_eval.py` builds the eval corpus, builds one
`RetrievalIndex`, and for each query runs three configurations against the
same index — BM25 alone, dense embeddings alone, and the full fused
(RRF + PageRank prior) + MMR pipeline — computing recall@k and MRR (cutoff
50) against the hand-verified expected node id. Reproduce with:

```bash
python eval/run_eval.py
```

**Result (measured 2026-09-16):**

| Config | recall@1 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|
| BM25 only | 0.30 | 0.75 | 0.85 | 0.474 |
| Embeddings only | 0.40 | 0.70 | 0.80 | 0.545 |
| **Full pipeline (fused + MMR)** | **0.70** | 0.75 | **0.90** | **0.739** |

The fused pipeline's recall@1 (0.70) more than doubles either signal alone
(0.30 / 0.40) — exactly the claim that combining lexical + semantic + a
PageRank prior beats either alone, measured rather than assumed. A few
queries were deliberately near-duplicate/hard cases (`get_cookie_domain` vs.
`get_cookie_httponly`, five very similarly-worded `sessions.py` methods) to
stress-test whether fusion actually helps on genuinely ambiguous queries,
not just easy ones.

## Token-reduction benchmark (claim #9)

**Method:** for the same 20 queries, compare tokens (OpenAI `cl100k_base`
encoding via `tiktoken`) under two conditions: **naive** = the whole file
containing the answer (a realistic fallback — grep for a name, read the
file it's in), **distill** = `search_code(query, k=5)`'s MMR-reranked
snippets. Reproduce with:

```bash
pip install -e ".[bench]"
python bench/token_reduction.py
```

**Result (measured 2026-09-16):**

| Metric | Value |
|---|---|
| Mean per-query reduction | **55.0%** |
| Per-query range | **-82.1% to 93.1%** |
| Aggregate (total distill tokens / total naive tokens) | **76.0%** reduction (90,450 → 21,700 tokens) |

## CI/CD, packaging, and registries (claim #15)

**Done, verified locally:**
- `pyproject.toml` builds a real sdist + wheel (`python -m build`), verified
  by installing the built wheel into a clean venv and confirming `distill
  --help` works from it — a real "would `pip install distill-mcp` work"
  check, not just "it has a pyproject.toml."
- `.github/workflows/ci.yml`: test job (pytest across Python 3.11/3.12) →
  build job (sdist/wheel + upload artifact) → publish-testpypi → publish-pypi
  on a `v*` tag push, using PyPI trusted publishing (OIDC), not a stored
  token.

**Not yet done — needs the user's accounts/credentials, not mine:**
- No GitHub remote has been pushed to yet (this repo is local-only), so the
  workflow has never actually run in CI.
- No PyPI/TestPyPI trusted-publisher configuration exists yet (requires a
  PyPI account + linking it to a real GitHub repo/workflow).
- No MCP Registry submission yet (requires deciding on and following its
  current submission process).

Per the playbook's fallback ladder ("drop the real PyPI/MCP Registry publish
→ keep it installable locally and demoable"): the package is genuinely
installable locally (`pip install -e .` and the built-wheel check above both
verified) and the CI/CD pipeline is written and locally validated, but "green
Actions run; package live on PyPI; registry entry exists" is not yet true.
The résumé wording should say "with CI/CD configured for PyPI and the MCP
Registry" until those three things are actually live.

**Honest caveat, not smoothed over:** 3 of the 20 queries show a *negative*
reduction — Distill returned more tokens than just reading the file. All
three are cases where the "naive" file is already small (554–1,388 tokens)
and a fixed `k=5` pulls in snippets from other, larger files that overshoot
it. Retrieval's benefit scales with how large/numerous the naive alternative
is — reading a 13,737-token file to serve a static file (93.1% reduction) is
where this actually earns its keep; a tiny single-purpose file needs no
retrieval at all. The résumé's "40–90%" range is close to but not exactly
this repo's measured range — the honest figure to use is **55% mean /
76% aggregate**, with the caveat that a naive small-file case can lose.
