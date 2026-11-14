# Person 3 implementation plan

**Goal:** Deliver AGENT-1/2 using the existing CLI and graph contracts.

**Architecture:** A selector merges graph evidence with an injectable retrieval interface. A small default Atlas adapter uses the existing autoEmbed index and stores run documents; Person 1 can substitute their helpers. A subprocess pytest recorder supplies collection IDs, phase outcomes, and counts. The orchestrator enforces checkout identity, runs selected/full tests, persists memory, and emits JSON/Markdown even on failures.

**Constraints:** No UI, Actions workflow, index provisioning, or automated checkout edits. Keep existing CLI flags and common Atlas fields. Work locally on `codex/test-selection-runner`, based on PR #2; publication is a separate step.

## Tasks

- [x] Selector: tests first for evidence merging/deduplication, top-three semantic matches per changed chunk, prior failed tests, retrieval errors, all graph fallback reasons, and no-candidate fallback. Define `RetrievalStore` plus `TestPlan`.
- [x] Runner: real subprocess tests for selective/full pytest, parameterization, assertion/setup/collection failures, empty suites, timeout, and counts. Collect head tests first and reject candidate IDs absent from collection. Enforce clean tracked checkout at head before execution.
- [x] Orchestration/CLI: tests first for report creation on pass/failure/fallback/input errors, persistence failure visibility, and exit status. Persist changed paths, chosen tests, outcomes, and searchable summaries as `kind=pr_run`. Missing credentials/retrieval must lead to full pytest, not success without execution.
- [x] Integration: document adapter/query/report fields and environment settings. Run full pytest and CLI/package checks, then request an independent review and resolve material findings.

## Decisions

- Query prior runs across the same repository's history (not just the current base); test search is scoped to the exact indexed base. Historical failures are revalidated against head collection.
- Similarity evidence records score/document identity; no unvalidated scientific cutoff is claimed. Top-ranked returned results follow the MVP design.
- Persistence failure is a visible report/CLI warning after tests; preserve the pytest exit status as required by ARCH.md. Memory cannot inform a later run until storage succeeds.
- The checkout must match head and have no tracked changes or untracked Python files. The runner never modifies it to meet that condition.
- `autoEmbed` is the default index name, configurable by environment. No live index is created here.

## Review record

- Independent review reproduced exit-zero hooks concealing failed outcomes and invalid Git inputs bypassing report-path protection. Regression tests now cover both fixes.
- Additional tests prevent early-success exits and runtime deselection from being reported as complete passing execution.
- A saved failed run is consumed by a later analysis in a real-Git/subprocess integration test; the database search boundary is doubled.
- Live Atlas graph test remains opt-in and skipped without its URI. Vector/index provisioning and Actions are not claimed verified.
- Final local suite: 61 passed, 1 skipped on Python 3.14.3.
