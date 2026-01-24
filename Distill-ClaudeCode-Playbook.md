# Distill — One-Day Sprint Playbook
### Build the whole thing today · concise notes · stay demoable

**Goal:** a running, demoable Distill by end of day — tree-sitter parsing across 8 languages, a real code graph, BM25 + dense embeddings fused with RRF, MMR re-ranking, a working MCP server, incremental re-indexing with content-addressed caching, a real test/eval suite, and (if time allows) a live PyPI + MCP Registry publish.

**How to use this:** put this file and `Distill-Build-Plan.md` in the repo. In Claude Code, say *"Follow PLAYBOOK.md in sprint mode. Set up PyPI/MCP Registry accounts and pick the target corpus first, then start Phase 0."* The Build Plan is the architecture / data model / claim-to-proof reference; this playbook is the timeboxed execution.

---

## Before you start (install/set up NOW — doing it mid-sprint burns the day)
- **Python 3.11+**, `pip`/`uv`, Git.
- An **embeddings API key** (OpenAI) in `.env` — or decide now to use a local `sentence-transformers` model instead (no key needed, slower first run).
- A **PyPI account** with an API token generated (Account Settings → API tokens). Also create a **TestPyPI** account/token — publish there first.
- Whatever the **MCP Registry**'s current submission process requires (account/manifest) — check it now, not at hour 8.
- Pick the **target corpus** (§8 of the Build Plan) — 1–4 real repos across several of the 8 languages, large enough to cross ~12K nodes.

## The one move that makes "today" realistic: start the slow things first
Nothing here is as slow as GKE provisioning, but three things are still worth
doing at **minute 0**, in parallel with Phase 0, because they're either
account-setup friction or genuinely manual work:

```bash
# minute 0, in parallel:
# 1. clone the target corpus (or corpora) now — this can be a large download
git clone <repo-1> corpora/repo-1
git clone <repo-2> corpora/repo-2   # add more if needed to cross ~12K nodes

# 2. create PyPI + TestPyPI accounts and API tokens now (UI step, do it first)
# 3. skim the MCP Registry's current submission requirements now
```
Also: **start drafting the ~30–50 labeled eval queries early** (Module/Phase 5
needs real human judgments — "which code node actually answers this query" —
and that's the one task in this whole project that can't be sped up by
Claude Code. Do a few queries per phase in spare moments rather than all at
once at the end.

---

## Sprint mode (how you, Claude Code, work today)
- Build in **phase-sized slices**, not tiny steps. Checkpoint + commit at each **phase boundary**.
- Keep explanations **brief: 2–3 sentences per new concept.** Write **one concise card per phase** in `docs/INTERVIEW_REVISION.md`.
- **One working happy path beats many half-features.** A pipeline that genuinely runs BM25→dense→RRF→MMR on real code beats five unfinished ranking strategies.
- Run autonomously within a phase; check in with me at phase boundaries.
- Tests alongside code. A flaky test blocks the phase; a merely-incomplete one doesn't — stub it, note it, keep moving, come back.

## `docs/INTERVIEW_REVISION.md` (keep it current, one card per phase)
```
## <Concept>
**One-liner:** ...
**Key points:** 3–5 bullets.
**Likely Q&A:** 2 questions + crisp answers.
```
Every card must match the code that exists — including the *real* measured numbers, not the résumé's placeholder numbers.

---

## Timeboxed plan (target ~7–9 focused hours)
- **~0.5h — Phase 0: Scaffold + corpus.** Package skeleton; CLI stub; target corpus cloned (kicked off at minute 0). Card: "Architecture overview."
- **~1.5h — Phase 1: Parsing + graph (8 languages).** tree-sitter parser per language; graph builder; SQLite graph store; index the corpus, report the real node/edge count. Cards: "tree-sitter / program analysis," "Code graph."
- **~1.5h — Phase 2: BM25 + embeddings + RRF.** Two independent rankings, fused. Cards: "BM25 vs. embeddings," "Reciprocal-rank fusion."
- **~1.0h — Phase 3: MMR + MCP server.** Diversity re-ranking; `search_code`/`get_symbol`/`get_context` tools; a real MCP client call working end to end. Cards: "MMR re-ranking," "MCP server."
- **~1.0h — Phase 4: Incremental indexing + caching.** Change detection; content-addressed cache. Card: "Incremental indexing / caching."
- **~1.5h — Phase 5: Eval suite + benchmarks.** Grow the real test suite; run the labeled retrieval eval (recall@k/MRR); run the token-reduction benchmark; write real numbers to `docs/BENCHMARKS.md`. Cards: "Retrieval-quality evaluation," "Token-reduction result (measured)."
- **~1.0h — Phase 6: CI/CD + publish.** GitHub Actions: test → build → publish to TestPyPI, then PyPI; submit to the MCP Registry. Card: "CI/CD + packaging."

## Fallback ladder (only if behind — cut from the bottom, in this order)
1. **Drop the real PyPI/MCP Registry publish** → keep it installable locally (`pip install -e .`) and demoable. Do the publish tomorrow; soften "to PyPI and the MCP Registry" on the résumé until it's live.
2. **Drop PageRank as a fusion input** → keep BM25 + embeddings + RRF + MMR (still a fully real, defensible pipeline). Note PageRank as "in progress" and don't claim it yet.
3. **Cap the eval set smaller** (say, 15–20 labeled queries instead of 30–50) → still real numbers, just a smaller sample; say so honestly in the revision card.
4. **Never drop:** the parsing → graph → BM25+embeddings+RRF → MMR → MCP server path, and at least one real measured number (token reduction or node count). That's the demoable, defensible core.

## What "done today" means (MVP — don't over-build)
- `distill index <corpus>` produces a real graph with a real node count.
- `distill serve` runs an MCP server; a real client call returns relevant, non-redundant snippets.
- At least one **measured** number in `docs/BENCHMARKS.md` (token reduction and/or recall@k).
- **Not today (unless time allows):** exhaustive language coverage beyond a solid subset of the 8, a large PyPI user base obviously, exotic re-ranking variants.

## Honesty check at wrap
Before we stop, tell me the **real** node/edge count, the **real** token-reduction range, the **real** test count, and whether PyPI/MCP Registry are actually live — so the résumé numbers match reality exactly, not the placeholders we started with.

---

## Start
Confirm prereqs, kick off the corpus clone + PyPI/TestPyPI account setup, then begin **Phase 0**. Work in sprint mode: build the slice, give me the 2–3 sentence explanation, write the phase card, commit — then move to the next phase.
