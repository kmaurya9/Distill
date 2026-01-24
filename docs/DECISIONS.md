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
