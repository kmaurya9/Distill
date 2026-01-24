# Distill — Build Plan (for Claude Code)

> **What it is:** an open-source **MCP server and code-retrieval engine** for
> coding agents. Point it at a repo; it parses the code into a **graph**,
> indexes it with **dense embeddings + BM25**, ranks nodes with **PageRank**,
> fuses the rankings with **reciprocal-rank fusion (RRF)**, then **re-ranks
> with MMR** to hand an agent a small, non-redundant, highly relevant set of
> code snippets — instead of dumping whole files into the prompt. That's what
> cuts LLM input tokens.
>
> **Why this file exists:** every phrase on the résumé line must be real and
> defensible in an interview. Build it in the phases below. Each phase ends in
> a runnable, verifiable state and names the exact résumé phrase it backs.
> Nothing here is decorative — each component earns its place.

---

## How to use this plan with Claude Code

- Work **phase by phase, top to bottom**. Each phase depends on the previous one.
- End every phase by running its **Definition of Done (DoD)**, then commit as `feat(phaseN): <summary>`.
- Maintain `docs/DECISIONS.md` (one short entry per non-obvious choice, with the "why") and `README.md` (how to run).
- Write tests **alongside** code. Retrieval-quality claims need a real labeled benchmark, not eyeballing.
- Keys (embedding API, PyPI token, MCP Registry token) come from `.env` / CI secrets — never hard-coded.
- "Prove X" means a real artifact: a passing test, or a number written to `docs/BENCHMARKS.md`. "It runs" is not proof.

---

## The contract: résumé claim → what proves it

The résumé lines are:

> *Shipped an open-source MCP retrieval layer for coding agents combining dense embeddings, BM25, PageRank, and reciprocal-rank fusion with MMR re-ranking over a 12K+ node code graph, cutting LLM input tokens 40–90%. Built indexing and evaluation infrastructure with tree-sitter AST parsing across 8 languages for program analysis, incremental re-indexing, content-addressed caching, and a 157-test regression and retrieval-quality evaluation suite with GitHub Actions CI/CD to PyPI and the MCP Registry.*

| # | Claim on the résumé | Made real by | Proof (the thing an interviewer could ask to see) |
|---|---------------------|--------------|-----------------------------------------------------|
| 1 | Open-source **MCP server** for coding agents | Python `mcp` SDK server exposing retrieval tools | Real MCP client call (e.g. from Claude Code) returns results |
| 2 | **Code-retrieval engine** | Full index → search pipeline | Integration test: query in, ranked snippets out |
| 3 | **Dense embeddings** | Embedding step over every graph node's content | Test: semantically similar snippets score highest |
| 4 | **BM25** | Lexical index over node text | Test: exact keyword match ranks top of the BM25 list alone |
| 5 | **PageRank** | Centrality over the call/import graph | Test: a heavily-called utility scores higher than a leaf function |
| 6 | **Reciprocal-rank fusion (RRF)** | Combines BM25 + dense (+ PageRank prior) into one ranking | Unit test verifies the RRF formula against a hand-computed toy case |
| 7 | **MMR re-ranking** | Diversity-aware re-rank of the fused list | Test: near-duplicate snippets get suppressed; diverse relevant ones kept |
| 8 | **12K+ node code graph** | AST-derived graph (files/classes/functions = nodes; calls/imports = edges) | Node/edge count reported from a real indexing run on the target corpus |
| 9 | **Cutting LLM input tokens 40–90%** | Token-count benchmark: naive context vs. Distill's MMR top-k | `docs/BENCHMARKS.md`: measured before/after tokens on a fixed task set |
| 10 | **tree-sitter AST parsing across 8 languages** | One parser module per language, tree-sitter grammars | Test: a sample file per language parses to the expected symbols |
| 11 | **Program analysis** | Symbol/call/import extraction from the AST | Test: a function's call graph is correctly extracted |
| 12 | **Incremental re-indexing** | Change detection (mtime/git-diff) reprocesses only changed files | Test: touching one file re-parses/re-embeds only that file's nodes |
| 13 | **Content-addressed caching** | Cache keyed by `hash(file content)` for parse + embedding results | Test: identical content at a different path/commit is a cache hit |
| 14 | **157-test regression and retrieval-quality evaluation suite** | Real pytest suite: unit + integration + a labeled retrieval benchmark | `pytest` output shows the count; `eval/run_eval.py` reports recall@k / MRR |
| 15 | **GitHub Actions CI/CD to PyPI and the MCP Registry** | Workflow: test → build → publish on tag | Green Actions run; package live on PyPI; entry in the MCP Registry |

If it's not in this table with a proof, it doesn't go on the résumé.

---

## 1. Architecture

```
                    ┌───────────────────────────┐
  coding agent      │   MCP Client (e.g. Claude  │
 (Claude Code, etc) │   Code, Cursor, custom)    │
                    └─────────────┬─────────────┘
                                  │ MCP protocol (stdio / SSE)
                                  ▼
                    ┌───────────────────────────┐
                    │   Distill MCP Server       │  tools:
                    │   (Python, `mcp` SDK)      │   search_code(query, k)
                    └─────────────┬─────────────┘   get_symbol(id)
                                  │                  get_context(file, line)
                                  ▼
                    ┌───────────────────────────┐
                    │   Retrieval Pipeline        │
                    │  ┌─────────┐  ┌──────────┐ │
                    │  │  BM25   │  │  Dense    │ │──▶ RRF fusion ──▶ MMR re-rank ──▶ top-k
                    │  │ (lexical)│  │ embeddings│ │
                    │  └─────────┘  └──────────┘ │
                    │        ▲ PageRank prior ▲   │
                    └────────┼───────┬─────────┘
                             │       │
                    ┌────────┴───┐ ┌─┴──────────────┐
                    │ Graph Store │ │ Vector + Cache  │
                    │ (nodes/edges│ │ Store (embeds,  │
                    │  SQLite)    │ │  content-hash   │
                    └────────▲────┘ │  cache)         │
                             │      └─────────────────┘
                    ┌────────┴──────────────┐
                    │  Indexing Pipeline      │
                    │  tree-sitter (8 langs)  │  incremental (mtime/git-diff)
                    │  → AST → symbols/edges  │  content-addressed cache
                    └─────────────────────────┘
                             ▲
                             │ walks
                    ┌────────┴──────────────┐
                    │  Target repo(s) on disk│
                    └────────────────────────┘
```

**Modules (one Python package, `distill/`):**

- **`indexing/`** — walks the target repo, parses each file with the language's tree-sitter grammar, extracts nodes (file / class / function) and edges (calls / imports / contains), and builds the code graph. Owns incremental re-indexing and content-addressed caching.
- **`retrieval/`** — BM25 index, dense embeddings, PageRank over the graph, RRF fusion, MMR re-ranking. Pure retrieval logic, no I/O framework concerns.
- **`store/`** — thin adapters: graph/metadata in SQLite, vectors in a local embedded index (FAISS or equivalent), cache table keyed by content hash.
- **`server/`** — the MCP server: wires retrieval into `search_code` / `get_symbol` / `get_context` tools.
- **`cli.py`** — `distill index <repo>` and `distill serve` for local use without an agent.

**Why each piece is here (so the claim is honest, not padding):**

- **BM25 + dense embeddings, fused with RRF** — lexical and semantic search fail differently (BM25 misses paraphrases, embeddings miss exact identifiers); fusing both is standard practice for retrieval quality, not decoration.
- **PageRank** — code isn't a flat bag of snippets; a function called from 40 places is usually more relevant context than one called from nowhere. Structural signal improves ranking beyond text similarity alone.
- **MMR** — the fused top-k is often near-duplicate (same function found three ways). MMR trims redundancy, which is *exactly* the mechanism that reduces tokens sent to the agent without losing coverage.
- **Content-addressed caching** — re-embedding unchanged code on every index run is wasted API spend and time; hashing content means identical code (even moved or duplicated) is never reprocessed.
- **Incremental re-indexing** — real repos change file-by-file; a full re-index on every commit doesn't scale. Only touched files get reprocessed.
- **MCP server, not a bespoke API** — the point is that *any* MCP-compatible agent can use it out of the box, which is what makes it a real developer tool rather than a one-off script.

---

## 2. Tech stack

- **Language:** Python 3.11+.
- **MCP:** the official `mcp` Python SDK (stdio and/or SSE transport).
- **Parsing:** `tree-sitter` + prebuilt grammars (`tree-sitter-languages` or per-language `tree-sitter-<lang>` packages) for: **Python, JavaScript, TypeScript, Java, Go, Rust, C, C++.**
- **Lexical search:** `bm25s` or `rank_bm25`.
- **Embeddings:** pluggable — OpenAI `text-embedding-3-small` by default, swappable for a local `sentence-transformers` model (keep it swappable so the tool doesn't hard-require a paid API).
- **Graph:** `networkx` for PageRank and traversal; persisted in **SQLite**.
- **Vector index:** `faiss-cpu` (or `chromadb` if simpler to wire) — embedded, no server required, so `pip install distill-mcp` stays self-contained.
- **Testing:** `pytest`, `pytest-cov`. Golden-file tests for parsers.
- **Packaging/publish:** `pyproject.toml` (hatchling or setuptools), **GitHub Actions**, **PyPI** (via `twine`/`uv publish`), and an entry in the **MCP Registry**.

> Record exact pinned versions in `docs/DECISIONS.md`.

---

## 3. Repository layout

```
distill/
├─ distill/
│  ├─ indexing/
│  │  ├─ parsers/           # one module per language (8 total)
│  │  ├─ graph_builder.py   # AST → nodes/edges
│  │  ├─ incremental.py     # change detection
│  │  └─ cache.py           # content-addressed cache
│  ├─ retrieval/
│  │  ├─ bm25_index.py
│  │  ├─ embeddings.py
│  │  ├─ pagerank.py
│  │  ├─ fusion.py          # RRF
│  │  └─ rerank.py          # MMR
│  ├─ store/
│  │  ├─ graph_store.py     # SQLite
│  │  └─ vector_store.py    # FAISS/Chroma
│  ├─ server/
│  │  └─ mcp_server.py      # search_code, get_symbol, get_context
│  └─ cli.py
├─ eval/
│  ├─ dataset/              # labeled query → relevant-node judgments
│  └─ run_eval.py           # recall@k, MRR, token-reduction benchmark
├─ tests/                   # the 157-test suite
├─ bench/                   # token-reduction benchmark harness
├─ docs/
│  ├─ DECISIONS.md
│  ├─ BENCHMARKS.md
│  └─ ARCHITECTURE.md
├─ .github/workflows/ci.yml
├─ pyproject.toml
└─ README.md
```

---

## 4. Data model

**Graph store (SQLite):**

```sql
CREATE TABLE nodes (
  id            TEXT PRIMARY KEY,       -- stable id (path + symbol + content hash)
  kind          TEXT NOT NULL,          -- FILE | CLASS | FUNCTION
  name          TEXT NOT NULL,
  file_path     TEXT NOT NULL,
  language      TEXT NOT NULL,
  start_line    INT, end_line INT,
  docstring     TEXT,
  content_hash  TEXT NOT NULL           -- for content-addressed caching
);

CREATE TABLE edges (
  src_id  TEXT NOT NULL REFERENCES nodes(id),
  dst_id  TEXT NOT NULL REFERENCES nodes(id),
  kind    TEXT NOT NULL,                -- CALLS | IMPORTS | CONTAINS
  PRIMARY KEY (src_id, dst_id, kind)
);

CREATE TABLE cache (
  content_hash TEXT PRIMARY KEY,
  parsed_json  TEXT,                    -- cached parse result
  embedding    BLOB                     -- cached embedding vector
);
```

**Vector store:** one entry per node id → embedding vector, backed by FAISS (or Chroma), rebuilt/updated incrementally alongside the graph store.

---

## 5. The retrieval pipeline (claims #3–7)

1. **BM25** over `name + docstring + content` per node → ranked list A.
2. **Dense embeddings** cosine similarity between query embedding and node embeddings → ranked list B.
3. **PageRank** precomputed once per index (over the call/import graph) → a per-node prior score.
4. **RRF fusion:** combine A and B (each contributes `1 / (k + rank)`), optionally weighted by the PageRank prior, into one ranked list.
5. **MMR re-rank:** iteratively pick the next result maximizing `λ · relevance − (1 − λ) · max similarity to already-picked results`, so the final top-k is relevant **and** non-redundant.
6. Return the top-k node contents (with file/line references) to the MCP tool caller.

**Test each stage in isolation** (BM25 alone, embeddings alone, RRF on a hand-built toy ranking, MMR on a set with known duplicates) before testing the pipeline end to end — this is what makes "combining X, Y, Z" a defensible sentence rather than a keyword list.

---

## 6. Indexing (claims #8, #10, #11, #12, #13)

- **Parsing (claim #10):** one parser module per language using tree-sitter; each extracts function/class/import nodes from the AST. Golden-file test per language: parse a known sample, assert the expected symbol list.
- **Program analysis (claim #11):** from the AST, extract call sites and import statements to build edges. Test: a function that calls two others produces two `CALLS` edges.
- **Graph scale (claim #8):** index a target corpus (see §8) large enough to cross **12,000 nodes**; report the actual node/edge count from a real run — don't assume, measure.
- **Incremental re-indexing (claim #12):** on re-run, compare each file's mtime/git-blob hash to the stored `content_hash`; only changed files are re-parsed. Test: modify one file, assert only its nodes are touched.
- **Content-addressed caching (claim #13):** before parsing or embedding, check `cache` for `content_hash`; hit → reuse; miss → compute and store. Test: duplicate content at a different path is a cache hit, not recomputed.

---

## 7. Evaluation suite (claims #9, #14)

**Two different things, both needed — don't conflate them:**

- **Regression tests** (`tests/`, target **157**): unit tests for each parser (8), graph builder, incremental indexing, caching, BM25, embeddings, PageRank, RRF, MMR, the MCP tool handlers, and a handful of end-to-end integration tests. Count them for real; don't pad to hit a number — if it lands at 140 or 170, that's the real count to put on the résumé.
- **Retrieval-quality benchmark** (`eval/`): a small **hand-labeled** set (~30–50 queries against the indexed corpus with the human-judged relevant node ids). Compute **recall@k** and **MRR** for: BM25-only, embeddings-only, and the full fused+MMR pipeline. This is what lets you say the fusion/re-ranking actually helps, not just that it runs.
- **Token-reduction benchmark (claim #9):** for a fixed set of realistic agent tasks, measure tokens sent to the LLM under two conditions — **naive** (e.g., whole relevant files, or raw grep hits) vs. **Distill** (MMR top-k). Report the % reduction range in `docs/BENCHMARKS.md` with the actual numbers observed. If it comes out at, say, 35–85%, that's the number to use — not 40–90% unless that's what you measured.

---

## 8. Target corpus (for the 12K+ node claim)

Pick one or a few real open-source repos spanning several of the 8 languages —
large enough in aggregate to cross ~12K nodes (a single mid-size repo often
isn't enough; combining 2–4 repos, or indexing a large monorepo, usually is).
Document exactly which repos/commits were indexed in `docs/BENCHMARKS.md` so
the number is reproducible.

---

## 9. Packaging, CI/CD, and registries (claim #15)

- `pyproject.toml` with console entry point `distill` → `distill.cli:main`.
- **GitHub Actions** (`.github/workflows/ci.yml`): on PR → lint + `pytest`; on tag push → build sdist/wheel, `twine upload` to **PyPI** (start with **TestPyPI** to prove the pipeline, then real PyPI).
- **MCP Registry:** publish the server's manifest per the registry's submission process so agents can discover it by name.

---

## 10. Execution phases (build in this order)

Each phase: **Objective → Tasks → Definition of Done → Justifies (claim #s).**

### Phase 0 — Scaffold
- **Objective:** installable package skeleton, empty but real.
- **Tasks:** repo layout (§3); `pyproject.toml`; CLI stub; pick and clone the target corpus (§8).
- **DoD:** `pip install -e .` works; `distill --help` runs.

### Phase 1 — Parsing + graph (8 languages)
- **Objective:** real AST parsing and a real graph.
- **Tasks:** tree-sitter parser module per language; graph builder (nodes/edges); SQLite graph store; index the target corpus.
- **DoD:** golden-file test passes per language; indexing the target corpus reports a real node/edge count.
- **Justifies:** #8, #10, #11.

### Phase 2 — Retrieval core (BM25 + embeddings + RRF)
- **Objective:** two independent rankings, fused.
- **Tasks:** BM25 index; embedding step + vector store; RRF fusion (optionally weighted by PageRank).
- **DoD:** unit tests for BM25-only, embeddings-only, and RRF-on-a-toy-case pass; a real query returns a fused ranked list.
- **Justifies:** #3, #4, #5, #6.

### Phase 3 — MMR + MCP server
- **Objective:** the pipeline is agent-usable.
- **Tasks:** MMR re-ranker; MCP server (`search_code`, `get_symbol`, `get_context`).
- **DoD:** a real MCP client call returns a relevant, non-redundant top-k; MMR test shows duplicate suppression.
- **Justifies:** #1, #2, #7.

### Phase 4 — Incremental indexing + caching
- **Objective:** re-indexing is cheap and correct.
- **Tasks:** content-hash cache; change detection for re-index.
- **DoD:** modifying one file only reprocesses that file's nodes; identical content elsewhere is a cache hit.
- **Justifies:** #12, #13.

### Phase 5 — Evaluation suite + benchmarks
- **Objective:** turn every number into something measured.
- **Tasks:** build out `tests/` to a real, counted suite; hand-label the retrieval eval set; run `eval/run_eval.py` for recall@k/MRR; run the token-reduction benchmark.
- **DoD:** `docs/BENCHMARKS.md` has the real test count, real recall@k/MRR numbers, and the real token-reduction range.
- **Justifies:** #9, #14.

### Phase 6 — CI/CD, PyPI, MCP Registry
- **Objective:** it's a real, installable, discoverable open-source tool.
- **Tasks:** GitHub Actions workflow; publish to TestPyPI then PyPI; submit to the MCP Registry.
- **DoD:** green Actions run; `pip install distill-mcp` works from PyPI; registry entry exists.
- **Justifies:** #15.

---

## 11. Bullet-justification checklist (final gate)

- [ ] **MCP server** — a real MCP client call returns results.
- [ ] **Code-retrieval engine** — end-to-end query → snippets integration test.
- [ ] **Dense embeddings** — semantic-similarity test passes.
- [ ] **BM25** — exact-keyword test passes.
- [ ] **PageRank** — centrality test passes.
- [ ] **RRF** — verified against a hand-computed toy case.
- [ ] **MMR** — duplicate-suppression test passes.
- [ ] **12K+ node graph** — real count from an actual indexing run, documented.
- [ ] **40–90% token reduction** — measured range in `docs/BENCHMARKS.md`, wording adjusted to match if different.
- [ ] **tree-sitter, 8 languages** — golden-file test per language.
- [ ] **Program analysis** — call/import edge extraction test.
- [ ] **Incremental re-indexing** — single-file-change test.
- [ ] **Content-addressed caching** — duplicate-content cache-hit test.
- [ ] **157-test suite** — real `pytest` count, adjusted to match if different.
- [ ] **Retrieval-quality evaluation** — recall@k / MRR reported for BM25-only vs. embeddings-only vs. full pipeline.
- [ ] **CI/CD to PyPI + MCP Registry** — green Actions run; package on PyPI; registry entry.

When every box is checked, the résumé line is fully defensible.

---

## 12. Running it

```bash
pip install -e .
distill index /path/to/target/corpus
distill serve                      # starts the MCP server (stdio)
# from an MCP-compatible client (e.g. Claude Code), add Distill as a server
# and call search_code("where do we validate auth tokens?")
```

---

## 13. Scope and honesty notes

- **The two numbers that must be measured, not assumed:** the node/edge count (claim #8) and the token-reduction range (claim #9). Whatever the real runs report is what goes on the résumé.
- **The test count is whatever `pytest` actually collects.** Don't write filler tests to hit 157 — write real ones and report the real number.
- **Retrieval quality needs real labels.** A recall@k number without a genuinely human-judged relevance set isn't evidence of anything; it's the most time-consuming part to do honestly, so budget for it.
- **Every dependency must stay load-bearing.** If PageRank or MMR turns out not to move the eval numbers, say so in `docs/DECISIONS.md` and reflect that honestly rather than keeping it for the résumé's sake.
- **Interview readiness is the real DoD:** you should be able to explain what RRF and MMR actually compute, why BM25+embeddings beats either alone, and show the eval numbers.
