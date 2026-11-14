# Local dashboard and Gemini implementation

User-approved scope: local Streamlit dark dashboard; index/analyze/results; prepared scenarios plus advanced paths/SHAs; pass/fail and honest measured timing; simple explanation default with developer toggle; automatic Gemini explanation using evidence, relevant code, and failure logs; deterministic fallback when Gemini is unavailable.

- [x] Add optional UI dependencies, a bounded explanation service returning both styles in one request, and redaction/grounding tests.
- [x] Add an explicit-action demo builder creating separate real Git repositories in a temporary directory, plus CLI-backed dashboard services and measured full-suite benchmarking.
- [x] Add the Streamlit screen, session-scoped results/explanations, downloads, and tests through AppTest. Never trigger analysis/API calls on a style toggle or ordinary rerun.
- [x] Update scope/contracts in PROBLEM, REQUIREMENTS, ARCH, and AGENTS to reflect the user's UI revision. Keep CLI analysis deterministic; Gemini only explains recorded decisions and cannot choose tests or change outcomes.
- [x] Run tests, launch loopback-only UI, and verify actual UI rendering. Live Gemini/Atlas calls require configured credentials; report their verification separately.

Decisions: a single Streamlit page over existing CLI; no web framework/API server. Time saved is measured against an explicit full-suite benchmark at the same repo/head and environment, otherwise unavailable. Demo results are actual runs, never fabricated. Existing team code and Atlas setup stay intact. New work stays local until publication is requested.

## Verification

- Local suite: 76 passed, 1 opt-in live test skipped before Atlas configuration. AppTest and the actual browser verified preparation, real pytest results, Simple default, and style switching without reanalysis.
- Independent review fixes cover quoted credential redaction, unexecuted-run timing, and missed-test-audit failure counts. Gemini SDK configuration and live generation of both styles verified with `gemini-3.1-flash-lite`; one-attempt retry bounding preserves fast template fallback.
- User explicitly approved a Cluster0-scoped `pr_impact_local` account with readWrite on `pr_impact` in Anshika's project. Credentials are in ignored, permission-restricted `.env`; trusted local CA configuration preserves TLS validation.
- Live Atlas verification succeeded: authenticated ping, READY/queryable `knowledge_vector` inspection, demo snapshot indexing, graph/vector-backed analysis with no fallback, passing actual tests, and persisted run lookup. The small demo selected all 13 cases; no reduction or performance improvement is claimed by this connection check.
- Dashboard restarted and browser verified Atlas configuration. No network allowlist changes or cluster provisioning occurred.
- Final publication checks: 77 local tests passed with one opt-in test skipped. Separate Atlas/Gemini-backed replay exercised pass, regression, and unmapped fallback; all runs saved memory. `docs/DEMO-REHEARSAL.md` records the measured overhead and the outstanding team Actions integration.
