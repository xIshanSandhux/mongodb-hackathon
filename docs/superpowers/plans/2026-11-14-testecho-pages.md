# TestEcho branding and page flow

User revision: name the product TestEcho; use MongoDB colors and visible Powered by MongoDB attribution; reduce vertical scrolling and advance between short pages for workflow decisions.

Implementation: native Streamlit pages for Setup → Knowledge → Run → Results, with separate Explanation, Tests, Timing, and Reports routes. Preparing a demo advances to Knowledge; indexing/choosing the existing snapshot advances to Run; completed analysis advances to Results. Existing CLI/Atlas/Gemini interfaces remain intact. Durable session configuration/results survive page changes. Inspection pages never trigger test execution or cloud requests. Main-page content stays compact; long evidence/logs use one selected record or bounded containers.

- [x] Replace the monolithic dashboard with short page handlers and routing.
- [x] Apply MongoDB navy/green colors, TestEcho identity, and Powered by MongoDB attribution.
- [x] Test page transitions, configuration/result persistence, default Simple view, and no reruns while inspecting results.
- [x] Update user-facing setup/docs, run full verification, and inspect the live browser.

Verification: 78 tests passed, one opt-in test skipped. AppTest exercised real prepare/analyze steps and automatic route changes, preserved configuration/results on Back navigation, and verified indexing executes once. Independent review found no important state/navigation regressions; agent logs remain available in the Reports selector. Native browser checks cover MongoDB colors, compact screens and attribution on a narrow viewport.
