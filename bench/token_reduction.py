"""Token-reduction benchmark (claim #9): for the same fixed set of realistic
agent tasks (eval/dataset/queries.json), measure LLM input tokens under two
conditions:

  naive   - the agent reads the whole file containing the answer (a common
            fallback when an agent doesn't have smart retrieval: grep for a
            name, then read the file it's in).
  distill - the agent calls search_code(query, k) and gets back only the
            MMR-reranked top-k snippets.

Usage: python bench/token_reduction.py
"""

from __future__ import annotations

import json
from pathlib import Path

import tiktoken

from distill.indexing.multi_repo import build_multi_repo
from distill.retrieval.embeddings import EmbeddingModel
from distill.retrieval.pipeline import RetrievalIndex
from distill.store.snippets import SnippetReader

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPORA = REPO_ROOT / "corpora"
QUERIES_PATH = REPO_ROOT / "eval" / "dataset" / "queries.json"
EVAL_REPOS = ["flask", "express"]
SEARCH_K = 5

ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def main() -> None:
    nodes, edges = build_multi_repo([CORPORA / r for r in EVAL_REPOS])
    embedding_model = EmbeddingModel()
    index = RetrievalIndex(embedding_model=embedding_model)
    index.build(nodes, edges, CORPORA)

    nodes_by_id = {n.id: n for n in nodes}
    reader = SnippetReader(CORPORA)
    queries = json.loads(QUERIES_PATH.read_text())

    naive_file_tokens_cache: dict[str, int] = {}
    rows = []
    for q in queries:
        file_path = q["file_path"]
        if file_path not in naive_file_tokens_cache:
            text = (CORPORA / file_path).read_text(encoding="utf-8", errors="replace")
            naive_file_tokens_cache[file_path] = count_tokens(text)
        naive_tokens = naive_file_tokens_cache[file_path]

        results = index.search(q["query"], k=SEARCH_K)
        distill_text = "\n\n".join(
            reader.read(nodes_by_id[node_id]) for node_id, _ in results if node_id in nodes_by_id
        )
        distill_tokens = count_tokens(distill_text)

        reduction = 1 - (distill_tokens / naive_tokens) if naive_tokens else 0.0
        rows.append((q["query"], naive_tokens, distill_tokens, reduction))

    print(f"{'query':<70}{'naive':>8}{'distill':>10}{'reduction':>12}")
    for query, naive_tokens, distill_tokens, reduction in rows:
        label = query if len(query) <= 68 else query[:65] + "..."
        print(f"{label:<70}{naive_tokens:>8}{distill_tokens:>10}{reduction:>11.1%}")

    reductions = [r[3] for r in rows]
    naive_total = sum(r[1] for r in rows)
    distill_total = sum(r[2] for r in rows)
    print()
    print(f"mean per-query reduction: {sum(reductions) / len(reductions):.1%}")
    print(f"min / max per-query reduction: {min(reductions):.1%} / {max(reductions):.1%}")
    print(f"aggregate reduction (total distill tokens / total naive tokens): "
          f"{1 - distill_total / naive_total:.1%}")
    print(f"total naive tokens: {naive_total}, total distill tokens: {distill_total}")


if __name__ == "__main__":
    main()
