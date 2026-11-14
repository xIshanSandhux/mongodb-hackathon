# Python graph indexing implementation plan

**Goal:** Deliver GRAPH-1 and GRAPH-2 against PROBLEM.md, REQUIREMENTS.md, and ARCH.md.

**Architecture:** Read immutable Git trees, parse with Python AST, and persist snapshot-scoped nodes/edges in Atlas. Traverse dependency-to-dependent edges with two-hop `$graphLookup`; reconstruct ordered evidence locally. Expose results to Person 3 rather than implementing their selector/runner.

**Constraints:** Python/pytest only; existing CLI flags and collection fields stay intact. No external writes except explicitly invoked indexing. No push or PR. Use the current checkout on a local feature branch.

## Tasks

- [x] 1. Write failing real-Git fixtures for commit-specific indexing, source/test extraction, relative/src imports, decorated methods, and malformed files. Implement `build_snapshot(repo, repo_id, commit)` in `indexer.py`, Git helpers in `gitrepo.py`, and typed results in `models.py`.
- [x] 2. Write failing graph tests for snapshot persistence, two-hop paths, cycles, changed/deleted/new files, stale/missing snapshots, and retrieval errors. Implement `AtlasGraphStore` in `graph_store.py` and `analyze_graph(repo, repo_id, base, head, store)`. Actual repository-isolation query execution is in the opt-in database test.
- [x] 3. Write CLI tests, wire `index` to Atlas using environment credentials, and preserve `analyze` for Person 3. Document exact fields/interfaces and limitations in ARCH.md, REQUIREMENTS.md, and a teammate handoff.
- [x] 4. Run full pytest, package/CLI smoke checks, and diff checks. Report actual live-Atlas limitations.

## Review focus

Test immutable commit reads despite dirty checkout; failed indexing must not mark a snapshot complete; preserve prior-run documents on reindex; two hops must not become three through zero-based depth; incomplete mappings and Atlas errors must signal fallback.

## Decisions

- Module nodes enable conservative file-level impact; source symbols remain separate semantic chunks. Test edges go directly to collected pytest function/method IDs.
- A completion document uses existing `kind=code` with `node_type=snapshot`, excluded from source retrieval via documented filters. Published last; absent after failed reindex.
- Serialize indexing/analysis per repo/snapshot in the MVP; concurrent reindex is not supported.
- External services are replaced only at their boundary in unit tests. Live Atlas verification requires credentials and is reported separately.

## Review and verification record

- Independent read-only review identified missing conftest relationships, missing module-level semantic context, and Python-to-symlink fallback. All three have regression tests and fixes.
- Snapshot invalidation now explicitly deletes the completion marker before bulk deletion, preventing a partial failed deletion from leaving a ready marker.
- Dependency installation succeeded in the local virtual environment; no dependency declarations changed.
- The live Atlas smoke test is opt-in; no test URI was available during local verification.
- Final local checks: 23 tests passed; one live database test skipped without `MONGODB_TEST_URI`. CLI help, installed dependency consistency, and `git diff --check` passed. Python 3.14.3 was used; other supported Python versions were not exercised.
