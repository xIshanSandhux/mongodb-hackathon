import pytest

from impact_agent.indexer import IndexingError, build_snapshot


def module(snapshot, path):
    return next(n for n in snapshot.nodes if n["path"] == path and n["node_type"] == "module")


def test_indexes_requested_commit_and_stable_test_ids(git_repo):
    repo, commit = git_repo
    base = commit({
        "src/shop/pricing.py": "def total(x):\n    return x * 2\n",
        "tests/test_pricing.py": "from shop.pricing import total\n\ndef test_total():\n    assert total(2) == 4\n",
    })
    (repo / "src/shop/pricing.py").write_text("invalid Python !!!")
    snapshot = build_snapshot(repo, "demo", base)
    test = next(n for n in snapshot.nodes if n["kind"] == "test")
    assert test["pytest_id"] == "tests/test_pricing.py::test_total"
    assert test["source_text"].startswith("def test_total")
    assert all(n["base_sha"] == base and n["repo_id"] == "demo" for n in snapshot.nodes)
    pricing = module(snapshot, "src/shop/pricing.py")
    assert "return x * 2" in pricing["source_text"]
    assert any(e["source_id"] == pricing["node_id"] and e["target_id"] == test["node_id"]
               and e["kind"] == "tested_by" for e in snapshot.edges)
    again = build_snapshot(repo, "demo", base)
    assert snapshot == again


def test_relative_imports_produce_dependency_to_dependent_edges(git_repo):
    repo, commit = git_repo
    sha = commit({
        "pkg/__init__.py": "from . import pricing\n",
        "pkg/pricing.py": "RATE = 2\n",
        "pkg/checkout.py": "from .pricing import RATE\n",
        "tests/test_checkout.py": "import pkg.checkout\n\ndef test_checkout():\n    pass\n",
    })
    snapshot = build_snapshot(repo, "demo", sha)
    pricing = module(snapshot, "pkg/pricing.py")
    checkout = module(snapshot, "pkg/checkout.py")
    assert any(e["source_id"] == pricing["node_id"] and e["target_id"] == checkout["node_id"]
               and e["kind"] == "imports" for e in snapshot.edges)
    init = module(snapshot, "pkg/__init__.py")
    assert any(e["source_id"] == pricing["node_id"] and e["target_id"] == init["node_id"]
               for e in snapshot.edges)


def test_extracts_decorated_async_tests_and_class_methods(git_repo):
    repo, commit = git_repo
    sha = commit({"test_api.py": (
        "import pytest\n@pytest.mark.parametrize('x', [1, 2])\n"
        "async def test_api(x):\n    pass\n\n"
        "class TestAPI:\n    def test_get(self):\n        pass\n\n"
        "class Helper:\n    def test_not_collected(self):\n        pass\n"
    )})
    snapshot = build_snapshot(repo, "demo", sha)
    tests = [n for n in snapshot.nodes if n["kind"] == "test"]
    assert {n["pytest_id"] for n in tests} == {"test_api.py::test_api", "test_api.py::TestAPI::test_get"}
    assert next(n for n in tests if n["symbol"] == "test_api")["source_text"].startswith("@pytest")


def test_rejects_incomplete_index_on_syntax_error(git_repo):
    repo, commit = git_repo
    sha = commit({"broken.py": "def nope(\n"})
    with pytest.raises(IndexingError, match="broken.py"):
        build_snapshot(repo, "demo", sha)


def test_snapshot_ids_are_isolated_but_node_ids_survive_commits(git_repo):
    repo, commit = git_repo
    base = commit({"a.py": "VALUE = 1\n"})
    head = commit({"a.py": "VALUE = 2\n"})
    a = module(build_snapshot(repo, "demo", base), "a.py")
    b = module(build_snapshot(repo, "demo", head), "a.py")
    other = module(build_snapshot(repo, "other", base), "a.py")
    assert a["node_id"] == b["node_id"]
    assert a["_id"] != b["_id"]
    assert a["node_id"] != other["node_id"]


def test_conftest_dependencies_reach_only_descendant_tests(git_repo):
    repo, commit = git_repo
    sha = commit({
        "tests/conftest.py": "import pytest\n@pytest.fixture\ndef setting():\n    return 1\n",
        "tests/sub/test_one.py": "def test_one(setting):\n    pass\n",
        "other/test_two.py": "def test_two():\n    pass\n",
    })
    snapshot = build_snapshot(repo, "demo", sha)
    fixture = module(snapshot, "tests/conftest.py")
    linked = [e["target_path"] for e in snapshot.edges if e["source_id"] == fixture["node_id"]]
    assert linked == ["tests/sub/test_one.py"]


def test_index_rejects_python_symlinks_instead_of_marking_incomplete_snapshot(git_repo):
    repo, commit = git_repo
    commit({"app.py": "VALUE = 1\n"})
    (repo / "link.py").symlink_to("app.py")
    sha = commit({"README.md": "fixture"})
    with pytest.raises(IndexingError, match="link.py"):
        build_snapshot(repo, "demo", sha)
