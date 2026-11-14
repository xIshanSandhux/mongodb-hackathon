"""Atlas storage and semantic retrieval for pull request analysis."""

import os
import time
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

VECTOR_INDEX = "knowledge_vector"


def create_atlas_client():
    """Connect using the environment or the project's local .env file."""
    load_dotenv()
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("Set MONGODB_URI before connecting to Atlas.")
    return MongoClient(uri, serverSelectionTimeoutMS=10000)


def atlas_database(client):
    return client[os.getenv("MONGODB_DATABASE", "pr_impact")]


def setup_atlas(db):
    """Create the collections and search index if they do not exist."""
    collections = set(db.list_collection_names())
    for name in ("knowledge", "edges"):
        if name not in collections:
            db.create_collection(name)

    knowledge = db["knowledge"]
    if not list(knowledge.list_search_indexes(VECTOR_INDEX)):
        knowledge.create_search_index(
            SearchIndexModel(
                name=VECTOR_INDEX,
                type="vectorSearch",
                definition={
                    "fields": [
                        {
                            "type": "autoEmbed",
                            "modality": "text",
                            "path": "search_text",
                            "model": "voyage-code-4",
                        },
                        *[
                            {"type": "filter", "path": field}
                            for field in ("repo_id", "base_sha", "kind")
                        ],
                    ],
                },
            )
        )


def _search(db, query, filters, limit):
    return list(db["knowledge"].aggregate([
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX,
                "path": "search_text",
                "query": {"text": query},
                "exact": True,
                "limit": limit,
                "filter": filters,
            }
        },
        {"$set": {"score": {"$meta": "vectorSearchScore"}}},
    ]))


def search_tests(db, *, repo_id, base_sha, query, limit=3):
    """Return test candidates from the indexed PR base snapshot."""
    return _search(
        db, query, {"repo_id": repo_id, "base_sha": base_sha, "kind": "test"}, limit
    )


def save_run(db, *, run_id, repo_id, base_sha, changed_paths,
             selected_test_ids, outcomes, search_text):
    """Save or replace a run so retries with the same ID are safe."""
    db["knowledge"].replace_one(
        {"_id": run_id},
        {
            "_id": run_id,
            "repo_id": repo_id,
            "base_sha": base_sha,
            "kind": "pr_run",
            "changed_paths": list(changed_paths),
            "selected_test_ids": list(selected_test_ids),
            "outcomes": outcomes,
            "search_text": search_text,
        },
        upsert=True,
    )


def search_prior_runs(db, *, repo_id, query, limit=3):
    """Retrieve similar runs across base snapshots of the same repository."""
    return _search(db, query, {"repo_id": repo_id, "kind": "pr_run"}, limit)


def smoke_test(db):
    """Verify both Atlas tickets with isolated, temporary demo records."""
    repo_id = f"atlas-smoke-{uuid4().hex}"
    test_id = f"{repo_id}-test"
    run_id = f"{repo_id}-run"
    query = "checkout discount reduces the order total"
    knowledge = db["knowledge"]
    try:
        knowledge.insert_one({
            "_id": test_id,
            "repo_id": repo_id,
            "base_sha": "demo-base",
            "kind": "test",
            "path": "tests/test_checkout.py",
            "symbol": "test_discount_applies",
            "search_text": f"Test that a {query}",
        })
        save_run(
            db,
            run_id=run_id,
            repo_id=repo_id,
            base_sha="older-base",
            changed_paths=["pricing.py"],
            selected_test_ids=[test_id],
            outcomes={test_id: "failed"},
            search_text=f"Pricing regression: {query}",
        )

        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            indexes = list(knowledge.list_search_indexes(VECTOR_INDEX))
            if indexes and indexes[0].get("status") == "FAILED":
                raise RuntimeError(f"Atlas index {VECTOR_INDEX} failed to build.")
            if indexes and indexes[0].get("queryable"):
                tests = search_tests(db, repo_id=repo_id, base_sha="demo-base", query=query)
                runs = search_prior_runs(db, repo_id=repo_id, query=query)
                if (
                    [record["_id"] for record in tests] == [test_id]
                    and [record["_id"] for record in runs] == [run_id]
                    and runs[0]["outcomes"][test_id] == "failed"
                ):
                    return
            time.sleep(5)
        raise TimeoutError("Atlas did not return both smoke-test records within five minutes.")
    finally:
        knowledge.delete_many({"_id": {"$in": [test_id, run_id]}, "repo_id": repo_id})


if __name__ == "__main__":
    with create_atlas_client() as client:
        database = atlas_database(client)
        setup_atlas(database)
        smoke_test(database)
    print("Verified filtered test search and prior-run retrieval in Atlas.")
