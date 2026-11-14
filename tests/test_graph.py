from pymongo.errors import ConnectionFailure

from impact_agent.graph import analyze_graph
from impact_agent.indexer import build_snapshot


class FixtureStore:
    """Only the database boundary is replaced; Git, AST, and path reconstruction are real."""

    def __init__(self, snapshot, status="ready"):
        self.snapshot = snapshot
        self.status = status

    def snapshot_status(self, repo_id, sha):
        return self.status

    def nodes(self, repo_id, sha, *, paths=None, node_ids=None):
        return [n for n in self.snapshot.nodes if n["repo_id"] == repo_id and n["base_sha"] == sha
                and (paths is None or n["path"] in paths)
                and (node_ids is None or n["node_id"] in node_ids)]

    def graph_rows(self, repo_id, sha, roots):
        # Mimic Atlas graphLookup depths, including the one-edge lookahead.
        rows = []
        for root in roots:
            frontier = {root}
            reachable, seen_edges = [], set()
            for depth in range(3):
                level = [edge for edge in self.snapshot.edges
                         if edge["source_id"] in frontier and edge["_id"] not in seen_edges]
                for edge in level:
                    seen_edges.add(edge["_id"])
                    reachable.append({**edge, "depth": depth})
                frontier = {edge["target_id"] for edge in level}
            # Reconstruction must handle unordered Atlas results and enforce
            # the two-edge candidate bound independently of this lookahead.
            rows.append({"node_id": root, "reachable": list(reversed(reachable))})
        return rows


def demo(git_repo):
    repo, commit = git_repo
    base = commit({
        "pkg/pricing.py": "RATE = 2\n",
        "pkg/checkout.py": "from pkg.pricing import RATE\n",
        "tests/test_checkout.py": "import pkg.checkout\ndef test_checkout():\n    pass\n",
    })
    return repo, commit, base, FixtureStore(build_snapshot(repo, "demo", base))


def test_graph_returns_two_hop_test_with_ordered_path_evidence(git_repo):
    repo, commit, base, store = demo(git_repo)
    head = commit({"pkg/pricing.py": "RATE = 3\n"})
    result = analyze_graph(repo, "demo", base, head, store)
    assert result.changed_paths == ["pkg/pricing.py"]
    assert not result.requires_full_suite
    assert [c["test_id"] for c in result.candidates] == ["tests/test_checkout.py::test_checkout"]
    evidence = result.candidates[0]["reasons"][0]
    assert evidence["changed_path"] == "pkg/pricing.py"
    assert [(e["source_path"], e["target_path"]) for e in evidence["edges"]] == [
        ("pkg/pricing.py", "pkg/checkout.py"), ("pkg/checkout.py", "tests/test_checkout.py")]
    assert any(n["source_text"] == "RATE = 3\n" for n in result.changed_chunks)


def test_graph_lookahead_requires_full_suite_when_path_exceeds_two_hops(git_repo):
    repo, commit = git_repo
    base = commit({
        "pkg/core.py": "VALUE = 1\n",
        "pkg/pricing.py": "from pkg.core import VALUE\n",
        "pkg/checkout.py": "from pkg.pricing import VALUE\n",
        "tests/test_checkout.py": "import pkg.checkout\ndef test_checkout():\n    pass\n",
    })
    store = FixtureStore(build_snapshot(repo, "demo", base))
    head = commit({"pkg/core.py": "VALUE = 2\n"})

    result = analyze_graph(repo, "demo", base, head, store)

    assert result.requires_full_suite
    assert "graph_truncated" in result.fallback_reasons
    # The third edge signals uncertainty; it is not used to build graph paths.
    assert "tests/test_checkout.py::test_checkout" not in {
        candidate["test_id"] for candidate in result.candidates
    }
    assert all(len(reason["edges"]) <= 2
               for candidate in result.candidates
               for reason in candidate["reasons"] if reason["kind"] == "graph")


def test_changed_tests_are_included_directly(git_repo):
    repo, commit, base, store = demo(git_repo)
    head = commit({"tests/test_checkout.py": "def test_checkout():\n    assert True\n"})
    result = analyze_graph(repo, "demo", base, head, store)
    assert result.candidates[0]["test_id"] == "tests/test_checkout.py::test_checkout"
    assert result.candidates[0]["reasons"][0]["kind"] == "changed_test"


def test_added_python_flags_unmapped_and_syntax_errors_flag_parse(git_repo):
    repo, commit, base, store = demo(git_repo)
    head = commit({"new.py": "X = 1\n", "pkg/pricing.py": "def broken(\n"})
    result = analyze_graph(repo, "demo", base, head, store)
    assert result.requires_full_suite
    assert any("unmapped" in r and "new.py" in r for r in result.fallback_reasons)
    assert any("parse" in r and "pkg/pricing.py" in r for r in result.fallback_reasons)


def test_deleted_source_traces_base_without_selecting_deleted_tests(git_repo):
    repo, commit, base, store = demo(git_repo)
    head = commit({"pkg/pricing.py": None, "tests/test_checkout.py": None})
    result = analyze_graph(repo, "demo", base, head, store)
    assert not result.requires_full_suite
    assert result.candidates == []
    assert result.changed_chunks


def test_missing_and_stale_snapshots_require_fallback(git_repo):
    repo, commit, base, store = demo(git_repo)
    head = commit({"pkg/pricing.py": "RATE = 9\n"})
    for status in ("missing", "stale"):
        store.status = status
        result = analyze_graph(repo, "demo", base, head, store)
        assert result.requires_full_suite
        assert status in result.fallback_reasons[0]
        assert result.changed_paths == ["pkg/pricing.py"]


def test_atlas_failure_is_sanitized_fallback(git_repo):
    repo, commit, base, store = demo(git_repo)
    head = commit({"pkg/pricing.py": "RATE = 5\n"})

    def fail(*args):
        raise ConnectionFailure("mongodb://user:secret@example.test")

    store.graph_rows = fail
    result = analyze_graph(repo, "demo", base, head, store)
    assert result.requires_full_suite
    assert result.fallback_reasons == ["atlas_retrieval_failed"]


def test_python_replaced_by_symlink_requires_fallback(git_repo):
    repo, commit, base, store = demo(git_repo)
    (repo / "pkg/pricing.py").unlink()
    (repo / "pkg/pricing.py").symlink_to("checkout.py")
    head = commit({"README.md": "fixture"})
    result = analyze_graph(repo, "demo", base, head, store)
    assert result.requires_full_suite
    assert any("unsupported_python" in r for r in result.fallback_reasons)


def test_cycles_are_bounded_and_multiple_reasons_are_retained(git_repo):
    repo, commit = git_repo
    base = commit({
        "a.py": "import b\nVALUE = 1\n", "b.py": "import a\n",
        "test_both.py": "import a\nimport b\ndef test_both():\n    pass\n",
    })
    head = commit({"a.py": "import b\nVALUE = 2\n", "b.py": "import a\nVALUE = 2\n"})
    store = FixtureStore(build_snapshot(repo, "demo", base))
    result = analyze_graph(repo, "demo", base, head, store)
    assert len(result.candidates) == 1
    reasons = result.candidates[0]["reasons"]
    assert {r["changed_path"] for r in reasons} == {"a.py", "b.py"}
    assert len(reasons) == 4  # direct and transitive path from each root
    assert all(len(r["edges"]) <= 2 for r in reasons)


def test_module_constants_are_retained_for_semantic_search(git_repo):
    repo, commit = git_repo
    base = commit({"app.py": "RATE = 1\ndef helper():\n    return 1\n"})
    head = commit({"app.py": "RATE = 5\ndef helper():\n    return 1\n"})
    store = FixtureStore(build_snapshot(repo, "demo", base))
    result = analyze_graph(repo, "demo", base, head, store)
    assert any("RATE = 5" in chunk["search_text"] for chunk in result.changed_chunks)


def test_source_imported_by_conftest_reaches_fixture_tests(git_repo):
    repo, commit = git_repo
    base = commit({
        "app.py": "RATE = 1\n",
        "tests/conftest.py": "from app import RATE\nimport pytest\n@pytest.fixture\ndef rate():\n    return RATE\n",
        "tests/test_rate.py": "def test_rate(rate):\n    assert rate == 1\n",
    })
    head = commit({"app.py": "RATE = 5\n"})
    result = analyze_graph(repo, "demo", base, head, FixtureStore(build_snapshot(repo, "demo", base)))
    assert [c["test_id"] for c in result.candidates] == ["tests/test_rate.py::test_rate"]
    assert len(result.candidates[0]["reasons"][0]["edges"]) == 2
