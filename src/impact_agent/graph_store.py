"""Atlas persistence and bounded dependency traversal (not vector retrieval)."""

from contextlib import contextmanager
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

from .indexer import stable_id
from .models import Document, Snapshot

SCHEMA_VERSION = 1


@contextmanager
def graph_store_from_env():
    """Open a bounded-time connection; never return credentials in diagnostics."""
    load_dotenv(Path.cwd() / ".env", override=False)
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("Set MONGODB_URI in the environment or local .env file.")
    with MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                     socketTimeoutMS=10000) as client:
        yield AtlasGraphStore(client[os.environ.get("MONGODB_DATABASE", "pr_impact")])


class AtlasGraphStore:
    def __init__(self, database):
        self.knowledge = database["knowledge"]
        self.edges = database["edges"]

    def save_snapshot(self, snapshot: Snapshot) -> None:
        scope = {"repo_id": snapshot.repo_id, "base_sha": snapshot.base_sha}
        # Removing the old marker first ensures a partial write is never ready.
        # MVP requires serialized index/analyze operations for each snapshot.
        self.knowledge.delete_one({**scope, "node_type": "snapshot"})
        self.knowledge.delete_many({**scope, "kind": {"$in": ["code", "test"]}})
        self.edges.delete_many(scope)
        if snapshot.nodes:
            self.knowledge.insert_many(snapshot.nodes)
        if snapshot.edges:
            self.edges.insert_many(snapshot.edges)
        self.knowledge.insert_one({
            "_id": stable_id(snapshot.repo_id, snapshot.base_sha, "<snapshot>"),
            **scope, "kind": "code", "node_type": "snapshot", "path": "",
            "symbol": "<snapshot>", "search_text": f"Indexed repository {snapshot.repo_id}",
            "complete": True, "schema_version": SCHEMA_VERSION,
            "node_count": len(snapshot.nodes), "edge_count": len(snapshot.edges),
        })

    def snapshot_status(self, repo_id: str, sha: str) -> str:
        scope = {"repo_id": repo_id, "node_type": "snapshot", "complete": True,
                 "schema_version": SCHEMA_VERSION}
        if self.knowledge.find_one({**scope, "base_sha": sha}):
            return "ready"
        return "stale" if self.knowledge.find_one(scope) else "missing"

    def nodes(self, repo_id: str, sha: str, *, paths=None, node_ids=None) -> list[Document]:
        query = {"repo_id": repo_id, "base_sha": sha,
                 "kind": {"$in": ["code", "test"]}, "node_type": {"$ne": "snapshot"}}
        if paths is not None:
            query["path"] = {"$in": list(paths)}
        if node_ids is not None:
            query["node_id"] = {"$in": list(node_ids)}
        return list(self.knowledge.find(query))

    def graph_rows(self, repo_id: str, sha: str, roots: list[str]) -> list[Document]:
        if not roots:
            return []
        scope = {"repo_id": repo_id, "base_sha": sha}
        return list(self.knowledge.aggregate([
            {"$match": {**scope, "node_id": {"$in": roots}, "node_type": "module"}},
            {"$graphLookup": {
                "from": self.edges.name,
                "startWith": "$node_id", "connectFromField": "target_id",
                "connectToField": "source_id", "as": "reachable",
                # Depths 0 and 1 are the two selection hops. Depth 2 is a
                # one-edge lookahead used only to detect a truncated graph.
                "maxDepth": 2, "depthField": "depth",
                "restrictSearchWithMatch": {**scope, "kind": {"$in": ["imports", "tested_by"]}},
            }},
        ]))
