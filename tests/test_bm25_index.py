from distill.retrieval.bm25_index import BM25Index


def test_exact_keyword_match_ranks_top():
    node_ids = ["n1", "n2", "n3"]
    texts = [
        "def validate_auth_token(token): check the token signature and expiry",
        "def render_template(name, context): return the rendered html page",
        "def compute_checksum(data): return a hash of the input bytes",
    ]
    index = BM25Index()
    index.build(node_ids, texts)

    results = index.search("validate auth token", k=3)
    assert results[0][0] == "n1"
    assert results[0][1] > results[1][1]
