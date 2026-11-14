from unittest.mock import MagicMock

import pytest

from impact_agent.graph_store import AtlasGraphStore
from impact_agent.models import Snapshot


def test_graph_query_is_snapshot_scoped_with_one_lookahead_hop():
    db = MagicMock()
    store = AtlasGraphStore(db)
    db.__getitem__.return_value.aggregate.return_value = iter([])
    assert store.graph_rows("demo", "base", ["root"]) == []
    pipeline = db.__getitem__.return_value.aggregate.call_args.args[0]
    assert pipeline[0]["$match"] == {"repo_id": "demo", "base_sha": "base", "node_id": {"$in": ["root"]}, "node_type": "module"}
    lookup = pipeline[1]["$graphLookup"]
    assert lookup["maxDepth"] == 2  # 0-1 are selected; 2 is a lookahead edge.
    assert lookup["connectFromField"] == "target_id"
    assert lookup["connectToField"] == "source_id"
    assert lookup["restrictSearchWithMatch"] == {"repo_id": "demo", "base_sha": "base", "kind": {"$in": ["imports", "tested_by"]}}


def test_snapshot_marker_is_last_and_prior_runs_are_not_deleted():
    db = MagicMock()
    knowledge, edges = MagicMock(), MagicMock()
    db.__getitem__.side_effect = {"knowledge": knowledge, "edges": edges}.__getitem__
    events = []
    knowledge.delete_one.side_effect = lambda query: events.append("invalidate")
    knowledge.delete_many.side_effect = lambda query: events.append("clear_nodes")
    knowledge.insert_many.side_effect = lambda docs: events.append("nodes")
    edges.insert_many.side_effect = lambda docs: events.append("edges")
    knowledge.insert_one.side_effect = lambda doc: events.append(doc)
    snapshot = Snapshot("demo", "base", [{"node_id": "a"}], [{"source_id": "a"}])
    AtlasGraphStore(db).save_snapshot(snapshot)
    assert events[:4] == ["invalidate", "clear_nodes", "nodes", "edges"]
    assert events[4]["node_type"] == "snapshot" and events[4]["complete"] is True
    deleted = knowledge.delete_many.call_args.args[0]
    assert deleted["kind"] == {"$in": ["code", "test"]}
    assert deleted["repo_id"] == "demo" and deleted["base_sha"] == "base"


def test_failed_write_never_publishes_completion():
    db = MagicMock()
    db.__getitem__.return_value.insert_many.side_effect = RuntimeError("write failed")
    with pytest.raises(RuntimeError):
        AtlasGraphStore(db).save_snapshot(Snapshot("demo", "base", [{"node_id": "a"}], []))
    db.__getitem__.return_value.insert_one.assert_not_called()
