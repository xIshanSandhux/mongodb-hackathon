import pytest

from impact_agent.indexer import IndexingError, build_snapshot
from impact_agent.graph import analyze_graph
from test_graph import FixtureStore


def files():
    return {
        "app/dependency_graph.py": "SERVICE_MODULES = {'vendor':'app.vendor', 'gateway':'app.gateway'}\nSERVICE_DEPENDENTS = {'vendor': {'gateway'}, 'gateway': set()}\n",
        "app/vendor.py": "VALUE = 1\n", "app/gateway.py": "VALUE = 1\n",
        "tests/test_gateway.py": "import app.gateway\ndef test_gateway():\n    pass\n",
        "tests/test_vendor.py": "import app.vendor\ndef test_vendor():\n    pass\n",
    }


def test_explicit_service_map_reaches_consumer_tests_with_evidence(git_repo):
    repo, commit = git_repo
    base = commit(files())
    snapshot = build_snapshot(repo, "demo", base)
    calls = [e for e in snapshot.edges if e["kind"] == "service_call"]
    assert len(calls) == 1
    assert (calls[0]["source_path"], calls[0]["target_path"]) == ("app/vendor.py", "app/gateway.py")
    assert calls[0]["evidence_path"] == "app/dependency_graph.py"
    head = commit({"app/vendor.py": "VALUE = 2\n"})
    impact = analyze_graph(repo, "demo", base, head, FixtureStore(snapshot))
    assert {c["test_id"] for c in impact.candidates} == {"tests/test_gateway.py::test_gateway", "tests/test_vendor.py::test_vendor"}
    gateway = next(c for c in impact.candidates if "gateway" in c["test_id"])
    assert gateway["reasons"][0]["edges"][0]["kind"] == "service_call"


def test_registry_is_literal_and_never_executed(git_repo):
    repo, commit = git_repo
    source = files()
    source["app/dependency_graph.py"] = "raise RuntimeError('must not run')\n" + source["app/dependency_graph.py"]
    sha = commit(source)
    assert any(e["kind"] == "service_call" for e in build_snapshot(repo, "demo", sha).edges)


def test_invalid_service_registry_cannot_publish_incomplete_graph(git_repo):
    repo, commit = git_repo
    source = files()
    source["app/dependency_graph.py"] = "SERVICE_MODULES = {'vendor':'missing.module'}\nSERVICE_DEPENDENTS = {'vendor': {'unknown'}}\n"
    sha = commit(source)
    with pytest.raises(IndexingError, match="service"):
        build_snapshot(repo, "demo", sha)


def test_service_map_change_requires_full_suite(git_repo):
    repo, commit = git_repo
    source = files()
    base = commit(source)
    snapshot = build_snapshot(repo, "demo", base)
    head = commit({"app/dependency_graph.py": source["app/dependency_graph.py"] + "# registry update\n"})
    impact = analyze_graph(repo, "demo", base, head, FixtureStore(snapshot))
    assert "service_metadata_changed" in impact.fallback_reasons


@pytest.mark.parametrize("mutation", [
    "SERVICE_DEPENDENTS['vendor'].add('gateway')",
    "SERVICE_DEPENDENTS['vendor'] = {'gateway'}",
    "SERVICE_DEPENDENTS.update({'vendor': {'gateway'}})",
    "SERVICE_CALLS = SERVICE_DEPENDENTS\nSERVICE_CALLS['vendor'].add('gateway')",
])
def test_dynamic_registry_mutations_cannot_be_silently_ignored(git_repo, mutation):
    repo, commit = git_repo
    source = files()
    source["app/dependency_graph.py"] += mutation + "\n"
    sha = commit(source)
    with pytest.raises(IndexingError, match="service"):
        build_snapshot(repo, "demo", sha)
