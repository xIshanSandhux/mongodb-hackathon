# PR Impact Agent MVP requirements and tickets

## Product outcome

For a pull request in one Python demo repository, produce an explainable regression-test plan, run the selected tests, report the outcome, and remember the run for future pull requests. When the system cannot account for the change, run the full pytest suite and explain why.

`PROBLEM.md` is the product intent. This file defines MVP acceptance criteria and ticket ownership. `ARCH.md` defines the implementation design. `AGENTS.md` gives Codex working instructions.

## Functional requirements

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Index one Python repository into Atlas. | `impact-agent index` at a commit stores source chunks, pytest test chunks, Python import edges, and test relationships. An Atlas vector query returns matching indexed content. |
| FR-02 | Identify changes for a PR. | `impact-agent analyze` accepts a repository path and base/head SHAs and reports the changed paths from that diff. |
| FR-03 | Select relevant tests using Atlas graph and vector search, plus prior-run memory. | A graph-linked change includes its dependent test; a test not found through the graph can be added by vector retrieval; a similar stored run can contribute a historically failing test. Every chosen test has a recorded reason. |
| FR-04 | Fall back when impact is uncertain. | Missing/stale base index, changed Python that cannot be parsed or mapped, Atlas retrieval failure, or zero defensible candidates causes the full pytest suite to run. The report states the fallback reason. |
| FR-05 | Execute tests and report results. | The CLI writes JSON and Markdown with SHAs, changed paths, tests, reasons, outcomes, duration, and fallback details, including on test failure. Test failure produces a nonzero CLI exit status. |
| FR-06 | Remember outcomes across PRs. | Each analysis stores its changed-path summary, selected tests, and outcomes in Atlas; a later similar analysis can retrieve the run. |
| FR-07 | Run from GitHub Actions. | A workflow in the separate demo repo supports `pull_request` and manual dispatch, passes the base/head SHAs and Atlas secret, always publishes the report in the Actions job summary, and fails the check when tests fail. |
| FR-08 | Demonstrate and measure the MVP. | The team can replay one graph-linked change, one semantic or memory match, and one uncertainty fallback, recording selected-test count, full-suite count, and elapsed time. |

## Non-functional requirements and exclusions

- Support Python and pytest only for the MVP.
- Use a Python CLI for the agent and GitHub Actions for CI triggering and output. No UI is required.
- Keep graph relationships, searchable code/test/run documents, and vector queries in MongoDB Atlas.
- Keep credentials out of source control. The demo workflow uses team-owned branches because ordinary Actions secrets are unavailable to fork PR workflows.
- Do not implement security-check findings, automated cleanup suggestions, multi-language support, PR comments, or a dashboard in the five-hour MVP.

## Four-person ticket breakdown

Replace Person 1–4 with teammate names at kickoff. First agree on the CLI flags and Atlas fields in `ARCH.md`; each owner can then work against the shared contract. Dependencies below are ticket dependencies, not reasons to block unrelated work: downstream owners should use stubs or seeded records until the dependency lands.

| Ticket | Owner | Depends on | Work and definition of done |
|---|---|---|---|
| ATLAS-1 | Person 1 | Kickoff contract | Create the `knowledge` and `edges` collections and the `autoEmbed` index on `knowledge.search_text` using `voyage-code-4`; prove a filtered vector query returns a seeded test document. |
| ATLAS-2 | Person 1 | ATLAS-1 | Implement Atlas helpers for filtered vector retrieval and storage/retrieval of prior-run documents; demonstrate that a saved run can be retrieved by a similar query. |
| GRAPH-1 | Person 2 | Kickoff contract, ATLAS-1 schema agreement | Build Python AST indexing for source chunks, pytest tests, imports, and test relationships; write knowledge nodes and edges using the agreed fields. |
| GRAPH-2 | Person 2 | GRAPH-1, ATLAS-1 | Read base/head diffs, resolve changed paths, and use bounded `$graphLookup` to return dependent code and tests with path evidence. |
| AGENT-1 | Person 3 | GRAPH-2, ATLAS-2 | Implement test-plan assembly from changed tests, graph results, vector candidates, and prior-run memory; deduplicate while retaining reasons; choose full-suite fallback for every FR-04 condition. |
| AGENT-2 | Person 3 | AGENT-1 | Run selected tests or full pytest, capture outcomes and duration, persist the run, emit JSON and Markdown reports even on test failure, and return a failing status when tests fail. |
| CI-1 | Person 4 | CLI contract from kickoff | Prepare the separate Python demo repo and Actions workflow for PR and manual runs; install the agent from a pinned commit, provide `MONGODB_URI` as a secret, pass event SHAs, publish the Markdown summary with an always-run step, and preserve a failed check when tests fail. |
| DEMO-1 | Person 4 | CI-1 plus integrated AGENT-2 | Add replayable changes and tests that show graph selection, semantic or memory retrieval, and fallback; run the Action end to end and record selected/full counts and timings. |

## Integration checkpoints

### GRAPH ticket integration details

GRAPH-1/2 use the **Implemented graph contract** in `ARCH.md`. Stable `node_id` differs from snapshot `_id`. The completion marker uses existing `kind=code`, `node_type=snapshot` and must be excluded from code vector results. Two-hop traversal uses MongoDB's zero-based `maxDepth=1`.

Graph acceptance includes committed-tree reads despite dirty worktrees, import and scoped conftest relationships, ordered path evidence, and fallback signals for missing/stale snapshots, unparseable/unmapped Python, unsupported Python symlinks, and Atlas errors. The handoff is `analyze_graph(...) -> GraphImpact`. Person 3 owns vector/memory merging, final no-candidate fallback, execution, and reports. Live graph verification requires `MONGODB_TEST_URI` and is separate from local tests.

### Team schedule

- **At 0:20:** CLI flags, collection fields, `repo_id`, snapshot commit behavior, and report fields are agreed.
- **By 2:30:** Atlas, graph indexing, selector/runner, and demo workflow can be exercised independently with stubs or seeded data.
- **By 3:45:** One PR Action runs analysis, pytest, report generation, and memory persistence end to end.
- **By 4:30:** The three demo scenarios work and the selected-versus-full suite measurements are captured.
- **By 5:00:** Reserve the remaining time for integration fixes and a presentation rehearsal.
