# PR Impact Agent architecture

## Goal and MVP boundary

The agent analyzes a pull request in a separate Python demo repository, selects likely regression tests, runs them, and explains the selection. It uses MongoDB Atlas for repository context, graph traversal, semantic search, and memory of earlier pull request outcomes. The MVP is a Python CLI invoked by GitHub Actions; it has no web UI.

The implementation is intentionally limited to one Python repository and pytest. Security checks and code-cleanup recommendations are follow-up work. See `PROBLEM.md` for the product goal and `REQUIREMENTS.md` for acceptance criteria and ticket ownership.

## Repositories and runtime flow

There are two repositories:

- **Agent repository:** this repository. It contains the Python package and CLI.
- **Demo repository:** a separate, team-controlled Python repository with sample application code, tests, and GitHub Actions workflows. Its workflow installs the agent from an immutable commit or release in the agent repository.

```mermaid
flowchart LR
    PR[Pull request in Python demo repo] --> GHA[GitHub Actions]
    GHA --> CLI[Python impact-agent CLI]
    CLI --> DIFF[Git diff and Python AST index]
    DIFF --> MDB[(MongoDB Atlas)]
    MDB --> GRAPH[Dependency graph traversal]
    MDB --> VECTOR[Vector and prior-run retrieval]
    GRAPH --> SELECT[Explainable test plan]
    VECTOR --> SELECT
    SELECT --> PYTEST[Run selected pytest tests or full suite]
    PYTEST --> REPORT[JSON report and Actions job summary]
    REPORT --> MEMORY[Persist PR and test outcomes in Atlas]
```

The default branch is indexed before PR analysis. A push to the demo repository's default branch refreshes its indexed snapshot; `workflow_dispatch` can run indexing or rehearse analysis manually. The PR workflow checks out enough Git history to compare the event's base and head SHAs. It only uses an index that matches the PR base SHA. If the snapshot does not match, analysis falls back to the full suite and reports that reason.

Use the normal `pull_request` event for the team-owned demo repository. Do not use `pull_request_target` to run code from a PR. The demo workflow stores `MONGODB_URI` as an Actions secret and uses a database user with only the needed access. The workflow installs the agent from a pinned commit so a run is reproducible. GitHub-hosted fork PRs do not receive ordinary repository secrets, so the hackathon demo uses branches in the team-owned repository.

## Components and interfaces

### Python CLI

Package the agent as an installable Python project with an `impact-agent` command.

```text
impact-agent index --repo <path> --repo-id <id> --commit <sha>
impact-agent analyze --repo <path> --repo-id <id> --base <sha> --head <sha> --output <json-path> --summary <markdown-path>
```

- `index` scans the Python demo repository at the specified commit, extracts source and pytest test chunks, derives import and test relationships, and writes a versioned snapshot to Atlas.
- `analyze` reads the base/head diff, looks up graph and semantic candidates, reads similar prior-run memories, runs the selected tests or the full suite, stores the outcome, and writes both a JSON report and a Markdown summary, including when tests fail.
- The report includes base and head SHAs, changed paths, chosen tests, selection reasons and evidence, test outcomes, elapsed time, whether fallback ran, and the fallback reason when present.
- The CLI exits successfully when the executed test command passes and with a nonzero status when it fails. This lets the Action publish the report and reflect the test result.

### Atlas collections

Use one database with two application collections:

- **`knowledge`:** Python source chunks, test chunks, and prior PR run summaries. Common fields are `repo_id`, `base_sha`, `kind` (`code`, `test`, or `pr_run`), `path`, `symbol`, and `search_text`. Code and test documents carry their source text and stable IDs. Run documents carry changed paths, selected test IDs, test outcomes, and a short searchable summary.
- **`edges`:** explicit dependency relationships. Each edge has `repo_id`, `base_sha`, `source_id`, `target_id`, and `kind` (`imports` or `tested_by`). Orient edges from a dependency to its dependent: a changed module is `source_id`, and an importing module or associated test is `target_id`.

Create a Vector Search `autoEmbed` index on `knowledge.search_text` with model `voyage-code-4`. Include filter fields for `repo_id`, `base_sha`, and `kind` so code, tests, and prior runs can be queried separately. Before the demo, verify the selected Atlas cluster supports the index, that the index is ready, and that an actual vector query returns results. Automated embedding model availability, billing, and index readiness are Atlas setup prerequisites.

### Test selection and fallback

1. Compute changed paths between the requested base and head commits.
2. Include changed pytest files directly.
3. Resolve changed Python modules to indexed node IDs and traverse `edges` with `$graphLookup`, bounded to two hops, to find dependent modules and tests.
4. For each changed code chunk, run a filtered Vector Search over test documents and add up to three highest-ranked test candidates. Query prior-run documents separately and add tests that failed on a semantically similar earlier change.
5. Deduplicate test IDs and retain a reason for each selection: changed test, graph path, semantic match, or prior regression.
6. Run the selected tests with pytest and store the report as a prior-run document for future analysis.

Run the full pytest suite when the base snapshot is missing or stale, a changed Python file cannot be parsed or matched to the index, Atlas graph/vector retrieval fails, or analysis produces no defensible test candidates. The report must identify the trigger. Do not silently present a fallback run as a focused selection.

## GitHub Actions output

The Action in the demo repository runs `impact-agent analyze` for PRs and supports manual dispatch. It captures the CLI step's exit status, then uses an `if: always()` step to append the Markdown summary to `$GITHUB_STEP_SUMMARY` and upload the JSON report. A final status step fails the workflow when the CLI reported failing tests. This preserves the explanation while keeping the check result accurate. The initial version does not post PR comments or require write access to the PR.

## Five-hour implementation sequence

| Elapsed time | Focus | Checkpoint |
|---|---|---|
| 0:00–0:20 | Agree on CLI flags, Atlas fields, demo repo, and Atlas connectivity | All owners can implement against the same contract. |
| 0:20–2:30 | Work tickets in parallel across Atlas, Python indexing/graph, selector/runner, and demo CI | Each component can be exercised against a stub or seeded data. |
| 2:30–3:45 | Integrate CLI with Atlas and the GitHub Action | One PR analysis runs from Action to pytest and emits a report. |
| 3:45–4:30 | Replay demo changes and compare selected tests with the full suite | Graph, semantic/memory, and fallback scenarios are demonstrated. |
| 4:30–5:00 | Fix integration blockers and rehearse the presentation | Clean final run and clear explanation of selection evidence. |

## Evaluation and deferred work

For the demo replay, record selected-test count, full-suite test count, elapsed time, and whether known failing tests were caught. Show reviewers the reason attached to each selected test. A small hackathon replay demonstrates the workflow but does not establish production recall or safety.

Defer multi-language parsing, a web dashboard, PR comments, security-check findings, cleanup suggestions, and broad historical benchmarking beyond the replayable demo.
