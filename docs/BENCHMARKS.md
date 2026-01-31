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

**Result (measured 2026-09-16):**

| Metric | Count |
|---|---|
| Total nodes | **33,129** |
| Total edges | **119,406** |
| — CONTAINS | 30,549 |
| — CALLS | 87,248 |
| — IMPORTS | 1,609 |
| FILE nodes | 2,580 |
| CLASS nodes | 3,672 |
| FUNCTION nodes | 26,877 |

Per-repo file counts by language: python 138, javascript 147, typescript 511,
java 264, go 99, rust 110, c 806, cpp 505.

Crosses the 12K+ node claim by a wide margin (33,129 nodes); even the largest
single repo alone (redis, 13,114 nodes) exceeds it.

**Known limitation:** CALLS/IMPORTS resolution is name-and-path based, not
type-resolved — a call to a common name (e.g. `init`) can match the wrong
same-named function within one repo if there are multiple candidates. This is
a documented tradeoff of lightweight static analysis without a type checker
per language (see `docs/DECISIONS.md`).

## Retrieval-quality evaluation (claim #14) — pending Phase 5

## Token-reduction benchmark (claim #9) — pending Phase 5
