# Repository instructions for Codex

## Read first

Before implementing or changing the PR Impact Agent, read these project documents in order:

1. `PROBLEM.md` for the product goal and success measures.
2. `REQUIREMENTS.md` for the MVP scope, acceptance criteria, and ticket ownership.
3. `ARCH.md` for the agreed components, data flow, interfaces, and fallback behavior.

Treat `PROBLEM.md` as the product intent, `REQUIREMENTS.md` as the MVP acceptance contract, and `ARCH.md` as the current technical design. If implementation evidence requires changing the design, update the relevant documents in the same change. Follow direct user instructions when they revise these documents.

## Product and scope

- Build an explainable pull request impact agent that selects and runs relevant regression tests.
- The five-hour MVP supports one Python demo repository, a Python CLI, MongoDB Atlas, and GitHub Actions. The demo repository is separate from this agent repository.
- Use Atlas for code/test knowledge, dependency edges, vector retrieval, and persisted prior-run outcomes.
- Keep core analysis and test execution in the CLI. GitHub Actions triggers the CLI and publishes its report. The user approved a local Streamlit dashboard and optional Gemini explanation layer; these wrap existing CLI behavior.
- Keep security-check findings and code-cleanup suggestions out of the MVP; they are later work described by `PROBLEM.md`.

## Implementation expectations

- Make test selection explainable from recorded evidence: changed paths, graph relationships, vector matches, and relevant prior runs.
- Run the full test suite when the indexed base snapshot is missing or stale, changed Python cannot be parsed or mapped, Atlas retrieval fails, or the impact analysis returns no defensible test candidates. Report why fallback occurred.
- A test failure must be visible in the CLI report and result in a failing process exit status so GitHub Actions reports the check as failed.
- Keep Atlas credentials and other secrets in environment variables or the hosting platform's secret store. Never commit credentials.
- Keep the Python parser scoped to the documented Python MVP. The approved UI is local-only, with Simple explanations by default and a Developer toggle. Do not add multi-language parsing, PR comments, security scanning, or automated code edits unless the user changes scope.
- Gemini explains recorded evidence after analysis; never let it alter test selection/results, request hidden internal thoughts, or fabricate time savings. Use template explanations on failure. Do not expose credentials through reports, source snippets, logs, or pytest environments.
- Preserve stable CLI inputs and Atlas document fields agreed in `ARCH.md`; update both architecture and requirements when changing them.
- Prefer small modules and explicit interfaces so the four tickets can integrate independently. Avoid dependencies that do not directly support the MVP.
- When code exists, run the relevant checks for the files changed and report what ran and any remaining limitation. Do not claim unrun checks passed.
