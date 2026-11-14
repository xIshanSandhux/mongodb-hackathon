# PayFlow integration

User requested testing and integrating ash-raf-codes/payment_processing_app into TestEcho. Inspect pinned source, run its real pytest suite, support its explicitly declared SERVICE_MODULES/SERVICE_DEPENDENTS map without executing source during indexing, then add PayFlow preparation to the existing short page flow.

- [x] Baseline: clone separately, inspect tests/workflow, install documented dependencies, and run full pytest.
- [x] Graph: test-first literal service-registry parsing and service_call edges, repo/snapshot filtering, schema readiness, and metadata-change fallback. Preserve two-hop selection plus truncation fallback.
- [x] Demo: fixed upstream URL and immutable commit; fresh separate clone per replay. Offer a behavior-preserving gateway edit, deliberate gateway regression, and real historical vendor PR comparison. Label local changes versus upstream commits. Keep small starter demos available.
- [x] Verify: full agent suite, actual PayFlow baseline/focused/regression tests, live Atlas analysis/storage, UI page preparation; document measured outcomes and limitations. Do not push changes to the payments repository.

Independent review found a literal-registry completeness gap for later mutation (.add/.update/subscript assignment and direct aliases). Added failing regression tests and rejection of those dynamic declarations. The real pinned PayFlow registry still indexes successfully with 28 service edges. Actual baseline: 55 passing tests. Live replay outcomes are recorded in docs/PAYFLOW-DEMO.md; source CI separately fails its Atlas connection check.

Final checks: 88 agent tests passed, one opt-in test skipped; live PayFlow pass/failure/upstream replay saved outcomes in Atlas, and Gemini explained the deliberate failure. Browser showed PayFlow payments as the primary demo. Source checkout remained clean, dependency consistency and credential scans passed.
