# Person 2: GRAPH-1 and GRAPH-2 handoff

## Delivered pieces

- `gitrepo.py`: resolve commits, read blobs, list changed paths without checkout or code execution.
- `indexer.py`: AST chunks; pytest IDs; absolute/relative/src imports; scoped conftest relationships.
- `graph_store.py`: Atlas snapshot persistence/readiness and bounded `$graphLookup` with a one-edge lookahead.
- `graph.py`: changed context, affected tests, ordered evidence, and fallback signals including `graph_truncated`.
- `cli.py`: working `impact-agent index`; `analyze` remains Person 3's scaffold.

`ARCH.md` defines the authoritative fields and interfaces. This is a conservative file-level import graph, not symbol-level call analysis.

## Index the demo repository

Install using README.md. Set `MONGODB_URI` and optional `MONGODB_DATABASE` (default `pr_impact`) in the environment or `.env` in your current directory.

```sh
impact-agent index --repo /absolute/path/to/demo-repo --repo-id demo-python --commit <base-sha>
```

It reads the exact commit, regardless of checkout edits. It writes `knowledge`/`edges`, not the vector index. Reindexing preserves prior runs and other snapshots. Serialize indexing and analysis of the same snapshot.

## Person 1 coordination

Edges reference stable `node_id`, not snapshot `_id`. Filter by `repo_id`, `base_sha`, and `kind`. Search text is in `search_text`; executable test IDs are in `pytest_id`. Exclude the completion marker from code search using `path != ""` or a node-type filter added to the vector index. It has existing `kind=code`, not a fourth kind.

Recommended ordinary indexes: `knowledge(repo_id, base_sha, node_id)`, `knowledge(repo_id, base_sha, path)`, and `edges(repo_id, base_sha, source_id)`. Vector search/index creation and prior-run memory remain your work.

## Person 3 usage

```python
from pathlib import Path
from impact_agent.graph import analyze_graph
from impact_agent.graph_store import graph_store_from_env

with graph_store_from_env() as store:
    impact = analyze_graph(
        Path("/absolute/path/to/demo-repo"),
        "demo-python", "<base-sha>", "<head-sha>", store,
    )

if impact.requires_full_suite:
    # Run full pytest; include impact.fallback_reasons in the report.
    pass
else:
    # Merge impact.candidates with vector/prior-run candidates.
    # Use impact.changed_chunks[*]["search_text"] for vector queries.
    # Full-suite fallback if final candidates are empty or retrieval fails.
    pass
```

Reuse an existing connection with `AtlasGraphStore(database)` if preferred. `analyze_graph` does not create a client. `dataclasses.asdict(impact)` gives a JSON-compatible object.

A candidate has this shape:

```json
{
  "test_id": "tests/test_checkout.py::test_checkout",
  "node_id": "<stable-node-hash>",
  "path": "tests/test_checkout.py",
  "reasons": [{
    "kind": "graph",
    "changed_path": "pkg/pricing.py",
    "edges": [
      {"source_path": "pkg/pricing.py", "target_path": "pkg/checkout.py", "kind": "imports"},
      {"source_path": "pkg/checkout.py", "target_path": "tests/test_checkout.py", "kind": "tested_by"}
    ]
  }]
}
```

Actual evidence also includes edge `repo_id`, `base_sha`, `source_id`, and `target_id`, omitted above for readability. Changed tests have a direct `changed_test` reason. Parameterized function IDs select all cases. New/renamed Python paths conservatively trigger fallback; removed test IDs are excluded.

Ensure the checkout is at head **before running tests**; graph analysis reads Git objects and does not enforce checkout state. Invalid Git inputs raise `GitError`; fail analysis with an honest diagnostic. The graph component does not run tests, store outcomes, or generate final reports.

## Verify

```sh
python -m pytest -q
impact-agent --help
impact-agent index --help
```

Local tests use real temporary Git repositories. Database-boundary tests verify query construction and write ordering; they do not prove a MongoDB server executes traversal correctly.

For the live test, set `MONGODB_TEST_URI` and optional `MONGODB_TEST_DATABASE` (default `pr_impact_test`):

```sh
python -m pytest tests/test_atlas_integration.py -q
```

It writes a generated `graph-smoke-...` repo ID and cleans up only that ID. It checks actual persistence/traversal, repository isolation, and prior-run preservation. Without the URI it is skipped. It does not verify Person 1's vector search.

## Graph cutoff behavior

Focused graph candidates and their evidence use at most two edges (Atlas depths 0 and 1). The query fetches depth 2 only as a lookahead. If that third edge exists anywhere in the reachable result, `analyze_graph` adds `graph_truncated` to `fallback_reasons`; Person 3 must run the full suite whenever `impact.requires_full_suite` is true. This is intentionally conservative and can cause a full-suite run even when the additional edge does not lead to another test.

## Demo limits

Use regular tracked Python files, root or `src/` packages, explicit imports, and standard pytest collection. Dynamic imports, custom discovery, inherited tests, plugins, monkeypatching, and unusual package roots are not modeled. Two-hop traversal is the agreed MVP candidate bound; deeper observed paths trigger full-suite fallback, but this is not proof of production regression recall.
