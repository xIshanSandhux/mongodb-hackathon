from copy import deepcopy

import pytest
from pymongo.errors import ConnectionFailure

from impact_agent.models import GraphImpact
from impact_agent.selection import assemble_plan


class Retrieval:
    def __init__(self, tests=(), runs=()):
        self.tests = list(tests)
        self.runs = list(runs)

    def search_tests(self, repo_id, base_sha, text, limit=3):
        return self.tests[:limit]

    def search_runs(self, repo_id, text, limit=3):
        return self.runs[:limit]


def test_document(name="test_app", score=0.8):
    return {"_id": name, "repo_id": "demo", "base_sha": "base", "kind": "test",
            "path": "tests/test_app.py", "pytest_id": f"tests/test_app.py::{name}",
            "node_id": name, "score": score}


# This is fixture data, not a test function.
test_document.__test__ = False


def impact():
    return GraphImpact("demo", "base", "head", changed_paths=["app.py"],
                       changed_chunks=[{"kind": "code", "path": "app.py", "symbol": "run",
                                        "search_text": "app.py run changed behavior"}])


def test_merges_graph_semantic_and_prior_failure_without_losing_reasons():
    graph = impact()
    graph.candidates = [{"test_id": "tests/test_app.py::test_app", "node_id": "test_app",
                         "path": "tests/test_app.py", "reasons": [{"kind": "graph", "edges": []}]}]
    before = deepcopy(graph)
    runs = [{"_id": "run1", "repo_id": "demo", "kind": "pr_run", "score": 0.9,
             "test_outcomes": [{"test_id": "tests/test_app.py::test_app", "outcome": "failed"},
                               {"test_id": "tests/test_app.py::test_other", "outcome": "error"},
                               {"test_id": "tests/test_app.py::test_passed", "outcome": "passed"}]}]
    plan = assemble_plan(graph, Retrieval([test_document()], runs))
    assert [c["test_id"] for c in plan.candidates] == ["tests/test_app.py::test_app", "tests/test_app.py::test_other"]
    assert {r["kind"] for r in plan.candidates[0]["reasons"]} == {"graph", "semantic_match", "prior_regression"}
    assert not plan.full_suite
    assert graph == before


def test_semantic_candidates_are_limited_to_three_per_chunk():
    plan = assemble_plan(impact(), Retrieval([test_document(f"test_{i}") for i in range(5)]))
    assert len(plan.candidates) == 3


@pytest.mark.parametrize("reason", ["missing_base_snapshot", "stale_base_snapshot", "cannot_parse_python: app.py",
                                  "unmapped_python: new.py", "unsupported_python: app.py", "atlas_retrieval_failed"])
def test_graph_uncertainty_always_requires_full_suite(reason):
    graph = impact()
    graph.fallback_reasons = [reason]
    plan = assemble_plan(graph, Retrieval([test_document()]))
    assert plan.full_suite and reason in plan.fallback_reasons


def test_retrieval_failure_overrides_existing_graph_candidates():
    graph = impact()
    graph.candidates = [{"test_id": "test_app.py::test_app", "path": "test_app.py", "reasons": [{"kind": "changed_test"}]}]

    class Broken(Retrieval):
        def search_runs(self, *args, **kwargs):
            raise ConnectionFailure("mongodb://secret")

    plan = assemble_plan(graph, Broken())
    assert plan.full_suite
    assert plan.fallback_reasons == ["atlas_retrieval_failed"]


def test_no_candidates_causes_full_suite():
    plan = assemble_plan(impact(), Retrieval())
    assert plan.full_suite and plan.fallback_reasons == ["no_defensible_candidates"]


def test_cross_repo_or_snapshot_matches_are_not_accepted():
    doc = test_document()
    doc["base_sha"] = "wrong"
    plan = assemble_plan(impact(), Retrieval([doc]))
    assert plan.full_suite and not plan.candidates


def test_memory_failure_does_not_accept_passed_tests():
    run = {"_id": "r", "repo_id": "demo", "kind": "pr_run", "score": 0.9,
           "test_outcomes": [{"test_id": "tests/test_app.py::test_passed", "outcome": "passed"}]}
    assert assemble_plan(impact(), Retrieval(runs=[run])).full_suite


def test_malformed_retrieval_evidence_requires_fallback():
    doc = test_document()
    del doc["_id"]
    plan = assemble_plan(impact(), Retrieval([doc]))
    assert plan.full_suite
    assert "invalid_retrieval_evidence" in plan.fallback_reasons
