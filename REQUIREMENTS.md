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
| FR-04 | Fall back when impact is uncertain. | Missing/stale base index, changed Python that cannot be parsed or mapped, Atlas retrieval failure, graph traversal beyond its two-edge selection bound, or zero defensible candidates causes the full pytest suite to run. The report states the fallback reason. |
| FR-05 | Execute tests and report results. | The CLI writes JSON and Markdown with SHAs, changed paths, tests, reasons, outcomes, duration, and fallback details, including on test failure. Test failure produces a nonzero CLI exit status. |
| FR-06 | Remember outcomes across PRs. | Each analysis stores its changed-path summary, selected tests, and outcomes in Atlas; a later similar analysis can retrieve the run. |
| FR-07 | Run from GitHub Actions. | A workflow in the separate demo repo supports `pull_request` and manual dispatch, passes the base/head SHAs and Atlas secret, always publishes the report in the Actions job summary, and fails the check when tests fail. |
| FR-08 | Demonstrate and measure the MVP. | The team can replay one graph-linked change, one semantic or memory match, and one uncertainty fallback, recording selected-test count, full-suite count, and elapsed time. |

## Non-functional requirements and exclusions

- Support Python and pytest only for the MVP.
- Keep core analysis in the Python CLI and GitHub Actions. The user additionally approved a local Streamlit dashboard for indexing, analysis, and results.
- Keep graph relationships, searchable code/test/run documents, and vector queries in MongoDB Atlas.
- Keep credentials out of source control. The demo workflow uses team-owned branches because ordinary Actions secrets are unavailable to fork PR workflows.
- Do not implement security-check findings, automated cleanup suggestions, multi-language support, or PR comments. The local dashboard is an explicitly approved scope extension.

## Approved dashboard and explanation extension

- Local-only Streamlit UI named TestEcho, using MongoDB green/navy colors and visible Powered by MongoDB attribution. Use short Setup → Knowledge → Run → Results pages with automatic advancement after successful actions; put explanations, evidence, timing, and reports on separate routes with bounded detail panels. Support prepared real-Git demo scenarios and local repository/base/head inputs; do not modify an existing repository's checkout.
- Lead with pass/fail counts, selected/full case counts, and measured time savings. Without a successful same-head full-suite benchmark, show time savings as unavailable. Negative savings must remain visible.
- Automatically generate Simple and Developer explanations in one Gemini request after each completed analysis. Simple is the default and uses judge-friendly language. Developer mode explains changed paths, graph evidence, similarity scores, prior regressions, and fallback reasons.
- Gemini may receive bounded report evidence, relevant committed Python snippets, and failure logs, with known credentials redacted. It cannot select tests, change results, or claim hidden internal reasoning. Display recorded evidence separately as authoritative.
- Missing credentials, API failures, or invalid generated output use template explanations and preserve results. UI reruns/style toggles must not rerun tests or call Gemini again.
- Keep API credentials in environment variables or ignored `.env`; no credential input fields or committed keys. `GEMINI_API_KEY`/`GOOGLE_API_KEY` are excluded from pytest subprocess environments.
- PayFlow (`ash-raf-codes/payment_processing_app`) is the primary prepared demo, pinned to an immutable upstream snapshot with separate local Git clones. Distinguish generated gateway refactor/regression commits from the historical vendor PR replay. Run the actual upstream pytest suite. Ingest its explicit static service registry as explainable `service_call` edges; malformed/dynamic registry metadata must not publish an incomplete index. Snapshot schema version 2 requires reindexing old snapshots. Registry-file changes trigger full-suite fallback. CLI flags and common Atlas fields remain stable.

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

GRAPH-1/2 use the **Implemented graph contract** in `ARCH.md`. Stable `node_id` differs from snapshot `_id`. The completion marker uses existing `kind=code`, `node_type=snapshot` and must be excluded from code vector results. Candidate selection is limited to two edges; MongoDB's zero-based `maxDepth=2` fetches one additional edge to signal `graph_truncated` and require full-suite fallback.

Graph acceptance includes committed-tree reads despite dirty worktrees, import and scoped conftest relationships, ordered path evidence, and fallback signals for missing/stale snapshots, unparseable/unmapped Python, unsupported Python symlinks, Atlas errors, and paths continuing beyond the two-edge bound. The handoff is `analyze_graph(...) -> GraphImpact`. Person 3 owns vector/memory merging, final no-candidate fallback, execution, and reports. Live graph verification requires `MONGODB_TEST_URI` and is separate from local tests.

### AGENT ticket integration details

AGENT-1/2 use **Implemented agent contract** in `ARCH.md`. Both CLI commands are implemented. Acceptance covers evidence-preserving graph/vector/prior-failure merging; mandatory and no-candidate fallback; real pytest case counts/outcomes; JSON/Markdown on test and analysis failure; nonzero test-failure status; and saved run documents consumable by later analyses. Index provisioning is still ATLAS-1; `RetrievalStore` is the replaceable ATLAS-2 boundary. Live vector/memory verification is pending a ready team index. Missing storage is reported as a warning while preserving the test result. Input/report-path errors do not execute tests or overwrite tracked files.

### Team schedule checkpoints

- **At 0:20:** CLI flags, collection fields, `repo_id`, snapshot commit behavior, and report fields are agreed.
- **By 2:30:** Atlas, graph indexing, selector/runner, and demo workflow can be exercised independently with stubs or seeded data.
- **By 3:45:** One PR Action runs analysis, pytest, report generation, and memory persistence end to end.
- **By 4:30:** The three demo scenarios work and the selected-versus-full suite measurements are captured.
- **By 5:00:** Reserve the remaining time for integration fixes and a presentation rehearsal.

With `analyze --audit-missed-tests`, run full pytest after a passing focused run. Report and persist failures from omitted tests when the audit completes. A failing or incomplete audit fails the check.
