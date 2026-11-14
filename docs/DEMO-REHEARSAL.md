# Local dashboard rehearsal — November 14, 2026

The dashboard wraps actual CLI/pytest runs. Atlas was verified against the approved `pr_impact` database in Anshika's Cluster0, and Gemini Flash Lite generated both Simple and Developer explanations for a real failing report. Credentials remain in ignored local `.env`, never in these artifacts.

## Measured replay

| Scenario | Result | Selected / full cases | Fallback | Shared memory | Total analysis | Full-suite baseline |
| --- | --- | --- | --- | --- | --- | --- |
| Focused behavior-preserving change | Passed | 1 / 13 | No | Saved | 4.71s | 0.61s |
| Introduced pricing regression | Failed, exit 1 | 1 / 13 | No | Saved | 2.87s | 0.62s |
| Added unmapped Python file | Passed | 13 / 13 | `unmapped_python` | Saved | 2.27s | 0.60s |

These are one-run local observations, not performance guarantees. Fewer cases did not mean lower end-to-end latency for this tiny suite: network/retrieval/collection overhead exceeded full-suite execution time. The dashboard correctly shows negative measured savings. Atlas embedding availability and retrieved candidates can change subsequent selections; the table records these runs only.

## Present the demo

1. Start `python -m streamlit run streamlit_app.py`, then open TestEcho at localhost:8501. Optional `.env` settings can preconfigure a rehearsed demo; temporary repos may disappear after OS cleanup.
2. On **Setup**, choose Focused change and **Prepare & continue**. **Knowledge → Index base in Atlas** advances to **Run → Run TestEcho**, then automatically to **Results**. Index readiness may lag; explain any actual fallback instead of claiming a focused run occurred.
3. Lead with result/counts, then open **Why these tests?** on its separate page; leave it on **Simple** for the judge. Switch to **Developer** to show graph paths, similarity evidence, and fallback details. Navigation and style switching do not rerun tests or Gemini.
4. Choose **Regression**, prepare/index/run it, and show the actual failing test, exit status, Gemini explanation, and saved-memory status.
5. Choose **Unmapped file fallback**, prepare/index/run, and explain why a new Python file caused the full suite to execute.
6. Open **Measure timing → Measure full suite** for a real comparison at the same commit; completion returns to Results. Do not claim time savings without a matching measurement.
7. Use the separate **Tests** and **Reports** pages for evidence/logs and JSON/Markdown downloads. Long details stay inside bounded panels. Gemini's generated explanation is advisory; recorded results remain authoritative. Service failures produce template explanations.

## What is and is not verified

- Automated local suite: 77 passed, one opt-in Atlas test skipped. Separate live checks verified Atlas authentication/index readiness, indexing, real analysis, and stored run lookup.
- Live Gemini succeeded with `gemini-3.1-flash-lite`. The prior Flash model returned temporary service errors; the UI now bounds Gemini to one request attempt before template fallback.
- AppTest verifies demo preparation, real analysis, Simple default, and style switching without a new run. Browser verification checks the actual localhost screen.
- The agent repository has no Actions workflow. The reviewed payments-demo PR (#7) is closed, and it does not supply an end-to-end workflow. A separately configured team demo repository and Actions secrets are still needed to establish CI-1/DEMO-1 end to end. No Actions success is claimed here.
