from unittest.mock import MagicMock

import pytest
from pymongo.errors import OperationFailure

from impact_agent.retrieval import AtlasRetrievalStore


def collection():
    c = MagicMock()
    c.list_search_indexes.return_value = [{"name": "autoEmbed", "status": "READY", "queryable": True}]
    c.aggregate.return_value = []
    return c


def test_test_query_uses_text_object_and_exact_snapshot_filters():
    c = collection()
    store = AtlasRetrievalStore(c)
    store.search_tests("demo", "base", "changed pricing")
    query = c.aggregate.call_args.args[0][0]["$vectorSearch"]
    assert query["query"] == {"text": "changed pricing"}
    assert query["filter"] == {"repo_id": "demo", "base_sha": "base", "kind": "test"}
    assert query["limit"] == 3 and query["index"] == "autoEmbed"


def test_memory_query_can_find_runs_from_older_base_snapshots():
    c = collection()
    AtlasRetrievalStore(c).search_runs("demo", "changed pricing")
    query = c.aggregate.call_args.args[0][0]["$vectorSearch"]
    assert query["filter"] == {"repo_id": "demo", "kind": "pr_run"}


def test_missing_or_building_index_is_an_error_not_empty_success():
    for indexes in ([], [{"name": "autoEmbed", "status": "BUILDING", "queryable": False}]):
        c = collection()
        c.list_search_indexes.return_value = indexes
        with pytest.raises(OperationFailure):
            AtlasRetrievalStore(c).search_tests("demo", "base", "change")


def test_run_storage_keeps_common_fields_and_outcomes():
    c = collection()
    document = {"_id": "run1", "repo_id": "demo", "base_sha": "base", "kind": "pr_run",
                "path": "", "symbol": "run1", "search_text": "pricing regression",
                "test_outcomes": [{"test_id": "test_app.py::test_price", "outcome": "failed"}]}
    AtlasRetrievalStore(c).save_run(document)
    args = c.replace_one.call_args
    assert args.args == ({"_id": "run1"}, document)
    assert args.kwargs == {"upsert": True}
