"""Opt-in real MongoDB graph smoke test; does not create a vector index."""

import os
import uuid

import pytest
from pymongo import MongoClient

from impact_agent.graph import analyze_graph
from impact_agent.graph_store import AtlasGraphStore
from impact_agent.indexer import build_snapshot


@pytest.mark.skipif(not os.environ.get("MONGODB_TEST_URI"), reason="Set MONGODB_TEST_URI for live graph verification")
def test_real_database_persistence_and_graphlookup(git_repo):
    repo, commit = git_repo
    base = commit({
        "pricing.py": "RATE = 1\n", "checkout.py": "from pricing import RATE\n",
        "test_checkout.py": "import checkout\ndef test_checkout():\n    pass\n",
    })
    head = commit({"pricing.py": "RATE = 2\n"})
    repo_id = "graph-smoke-" + uuid.uuid4().hex
    with MongoClient(os.environ["MONGODB_TEST_URI"], serverSelectionTimeoutMS=5000) as client:
        db = client[os.environ.get("MONGODB_TEST_DATABASE", "pr_impact_test")]
        store = AtlasGraphStore(db)
        try:
            store.save_snapshot(build_snapshot(repo, repo_id, base))
            assert store.snapshot_status(repo_id, base) == "ready"
            result = analyze_graph(repo, repo_id, base, head, store)
            assert not result.requires_full_suite
            assert [c["test_id"] for c in result.candidates] == ["test_checkout.py::test_checkout"]
            assert len(result.candidates[0]["reasons"][0]["edges"]) == 2
            assert store.snapshot_status("unrelated-" + repo_id, base) == "missing"
            run = {"repo_id": repo_id, "base_sha": base, "kind": "pr_run", "search_text": "prior regression"}
            db.knowledge.insert_one(run)
            store.save_snapshot(build_snapshot(repo, repo_id, base))
            assert db.knowledge.count_documents({"repo_id": repo_id, "kind": "pr_run"}) == 1
        finally:
            db.knowledge.delete_many({"repo_id": repo_id})
            db.edges.delete_many({"repo_id": repo_id})
