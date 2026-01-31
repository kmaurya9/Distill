from distill.indexing.multi_repo import build_multi_repo


def _write(root, rel_path, content):
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_same_name_functions_do_not_resolve_across_repos(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _write(repo_a, "main.py", "def main():\n    return helper()\n\ndef helper():\n    return 1\n")
    _write(repo_b, "main.py", "def main():\n    return helper()\n\ndef helper():\n    return 2\n")

    nodes, edges = build_multi_repo([repo_a, repo_b])

    # ids are namespaced per repo, so no collisions
    ids = [n.id for n in nodes]
    assert len(ids) == len(set(ids))

    calls = {(e.src_id, e.dst_id) for e in edges if e.kind == "CALLS"}
    a_main = next(n for n in nodes if n.id.startswith("repo_a") and n.name == "main")
    a_helper = next(n for n in nodes if n.id.startswith("repo_a") and n.name == "helper")
    b_main = next(n for n in nodes if n.id.startswith("repo_b") and n.name == "main")
    b_helper = next(n for n in nodes if n.id.startswith("repo_b") and n.name == "helper")

    assert (a_main.id, a_helper.id) in calls
    assert (b_main.id, b_helper.id) in calls
    # no cross-repo edges
    assert (a_main.id, b_helper.id) not in calls
    assert (b_main.id, a_helper.id) not in calls
