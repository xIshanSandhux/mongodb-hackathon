# AGENT-1 and AGENT-2 handoff

## Run the completed CLI

Install the agent and the demo repository's dependencies into the same Python environment. Configure `MONGODB_URI`, optional `MONGODB_DATABASE` (default `pr_impact`), and optional `MONGODB_VECTOR_INDEX` (default `knowledge_vector`) in environment variables or `.env` in your working directory.

Index the exact base commit, then analyze with the demo checked out at head:

```sh
impact-agent index --repo /path/to/demo --repo-id demo-python --commit <base-sha>
impact-agent analyze --repo /path/to/demo --repo-id demo-python --base <base-sha> --head <head-sha> --output impact-report.json --summary impact-summary.md
```

The checkout must have no tracked changes or untracked Python files. No checkout/edit happens automatically. Report paths must be distinct and must not overwrite tracked files. Keep generated reports outside committed demo source, or ignore them in the demo repository.

## Implemented behavior

1. Keep direct changed-test and graph-path evidence.
2. Retrieve up to three semantic test matches per distinct changed code chunk.
3. Retrieve similar prior runs and include tests with actual failed/error outcomes.
4. Deduplicate IDs while retaining every evidence source.
5. Use full pytest for graph uncertainty, retrieval failure, malformed evidence, missing candidate IDs, or zero candidates.
6. Collect the head suite for case IDs/counts, then run the chosen cases in a subprocess.
7. Write JSON and Markdown, persist the outcome in `knowledge`, and return pytest's status.

Reports distinguish real test failure, collection/setup errors, no tests, timeout, and input errors. Passing tests with unavailable Atlas still use full-suite fallback and explicitly report that memory was not saved. Failed memory writes are warnings, not passing-memory claims. Input errors produce reports when destinations are valid; unsafe destinations fail without overwriting source.

## Person 1: replaceable Atlas boundary

`AtlasRetrievalStore(knowledge_collection, index_name="autoEmbed")` is a small default adapter. It uses the existing index; it does not provision one. Test queries filter exact `repo_id`, `base_sha`, `kind=test`; run queries filter `repo_id`, `kind=pr_run` across historical bases. A missing/building index must raise an error, not silently return no matches while the graph narrows selection.

The replaceable `RetrievalStore` methods are:

```python
search_tests(repo_id, base_sha, text, limit=3) -> list[dict]
search_runs(repo_id, text, limit=3) -> list[dict]
save_run(document) -> None
```

Test matches contain `_id`, `repo_id`, `base_sha`, `kind=test`, `pytest_id`, optional stable `node_id`, and numeric `score` in [0, 1]. Run matches contain `_id`, `repo_id`, `kind=pr_run`, `score`, and `test_outcomes=[{"test_id": "...", "outcome": "failed"}]`. Only `failed` and `error` outcomes add historical tests. Propagate PyMongo errors so retrieval becomes a full-suite fallback. Malformed documents also cause fallback.

Run documents include the existing common fields plus `head_sha`, `created_at`, `changed_paths`, `change_summary`, `selected_test_ids`, `selection_evidence`, `test_outcomes`, `fallback`, `test_status`, `exit_code`, and `duration_seconds`. IDs for executed outcomes include parameter case suffixes. Saved runs are upserted by a unique per-analysis `_id`.

**Still required from Atlas:** provision/verify the autoEmbed index on `search_text`, with filter fields for repo/base/kind, then verify test and run searches on the real cluster. The default adapter checks index readiness; its user needs permissions to inspect search indexes as well as read/write knowledge.

## Person 4: CI handoff

Install the agent from a pinned commit containing AGENT-1/2 (PR #2 alone contains only graph work). Check out the demo head with history containing base. Pass event SHAs and the Atlas secret through the documented flags/environment. Publish `impact-summary.md` and upload `impact-report.json` with always-run steps. Preserve the CLI's failing exit status. Do not assume reports exist if the interpreter never starts or the destinations are unwritable.

The JSON `exit_code` and `test_status` describe the executed tests; `fallback` explains broad execution; `persistence.status` independently describes memory storage. `selected_test_count` and `full_suite_count` count pytest cases, not functions; `collection_duration_seconds` and `test_duration_seconds` separate collection overhead from execution. Do not present collection-only counts as a full-suite timing baseline.

The agent disables pytest `addopts` and `PYTEST_ADDOPTS` to avoid hidden `-k`, `-x`, or parallel-run options altering the plan. Standard project configuration/plugins remain enabled. Use ordinary pytest collection for the MVP. Tests must complete within the default 300-second limit (collection: 60 seconds).

## Verification and remaining limits

```sh
python -m pytest -q
impact-agent analyze --help
```

Local tests exercise real Git trees and subprocess pytest for selected/full runs, failures, parameterization, fixtures, collection errors, timeout, report generation, and later reuse of a saved failure. Retrieval and persistence use database-boundary doubles in these tests. Live Atlas vector scoring/readiness/eventual indexing and end-to-end Actions remain unverified. No relevance threshold or regression-recall claim is established by these fixtures.
