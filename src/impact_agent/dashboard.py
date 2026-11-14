"""Single-page local dashboard over the agent's deterministic CLI."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from .dashboard_service import SCENARIOS, analyze_local, benchmark_full_suite, dashboard_metrics, index_local, prepare_demo
from .explanations import explain_report


def main():
    load_dotenv(Path.cwd() / ".env", override=False)
    st.set_page_config(page_title="PR Impact Agent", page_icon="◈", layout="wide")
    st.markdown("""<style>
    .block-container {max-width:1250px;padding-top:2.6rem}
    div[data-testid="stMetric"] {background:#141d32;border:1px solid #26334d;border-radius:12px;padding:18px}
    h1 {letter-spacing:-1.5px} div[data-testid="stCaptionContainer"] {color:#9eacc4}
    </style>""", unsafe_allow_html=True)
    st.caption("◈  PR IMPACT AGENT  /  LOCAL WORKSPACE")
    st.title("Know what your change could break.")
    st.write("Relevant tests. Recorded evidence. A clear explanation for everyone.")
    with st.sidebar:
        st.title("Your workspace")
        mode = st.radio("Repository", ["Prepared demo", "Local repository"], key="repository_mode")
        st.divider()
        st.caption("CONNECTED SERVICES")
        st.write("Atlas: " + ("credentials configured" if os.environ.get("MONGODB_URI") else "not configured"))
        st.write("Gemini: " + ("key configured" if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") else "template explanations"))
        st.caption("Configuration status does not verify a live connection.")
        st.caption("Set credentials in your local .env. They are never entered into a report.")

    if mode == "Prepared demo":
        left, right = st.columns([3, 1])
        scenario = left.selectbox("Demo scenario", SCENARIOS)
        right.write("")
        if right.button("Prepare demo", key="prepare", use_container_width=True):
            try:
                with st.spinner("Preparing a separate demo repository…"):
                    demo = prepare_demo(scenario)
                st.session_state.update(repo_path=str(demo.repo), repo_id=demo.repo_id, base=demo.base, head=demo.head)
                st.session_state["prepared_scenario"] = scenario
                for key in ("result", "explanation", "baseline", "summary", "action_log"):
                    st.session_state.pop(key, None)
                st.success("Demo prepared. Index its base with Atlas, or run now to see full-suite fallback.")
            except Exception:
                st.error("Could not prepare the demo. Check Git and temporary-directory access.")
        st.caption("Focused change preserves behavior. Regression introduces a real failing test. Unmapped file demonstrates conservative fallback.")
        if st.session_state.get("prepared_scenario") and st.session_state["prepared_scenario"] != scenario:
            st.info("Click Prepare demo to switch scenarios. The current repository and results still belong to "
                    + st.session_state["prepared_scenario"] + ".")

    with st.expander("Repository and commit settings", expanded=mode == "Local repository"):
        st.text_input("Repository path", key="repo_path", value=os.environ.get("IMPACT_DEMO_REPO", ""))
        st.text_input("Repository ID", key="repo_id", value=os.environ.get("REPO_ID", "demo-python"))
        c1, c2 = st.columns(2)
        c1.text_input("Base commit", key="base", value=os.environ.get("IMPACT_DEMO_BASE", "HEAD^"))
        c2.text_input("Head commit", key="head", value=os.environ.get("IMPACT_DEMO_HEAD", "HEAD"))
        st.caption("The repository must already be checked out cleanly at the head commit. The app does not change your checkout.")
    repo_text = st.session_state.get("repo_path", "").strip()
    repo_id = st.session_state.get("repo_id", "").strip()
    base, head = st.session_state.get("base", "").strip(), st.session_state.get("head", "").strip()
    ready = bool(repo_text and repo_id and base and head)
    context = (repo_text, repo_id, base, head)
    a, b, c = st.columns([1, 1.3, 1.5])
    index_clicked = a.button("1 · Index base", key="index", disabled=not ready, use_container_width=True)
    analyze_clicked = b.button("2 · Run analysis", key="analyze", type="primary", disabled=not ready, use_container_width=True)
    benchmark_clicked = c.button("Measure full-suite baseline", key="benchmark", disabled=not ready, use_container_width=True)
    if index_clicked:
        try:
            with st.spinner("Indexing committed code and tests in Atlas…"):
                message = index_local(Path(repo_text), repo_id, base)
            st.success(message)
            st.info("Atlas embeddings may still be building. Analysis will fall back if retrieval is not ready.")
        except (RuntimeError, OSError) as exc:
            st.error(str(exc))
    if analyze_clicked:
        try:
            with st.spinner("Analyzing the change and running tests…"):
                report, summary, log = analyze_local(Path(repo_text), repo_id, base, head)
            st.session_state.update(result=report, summary=summary, action_log=log, result_context=context)
            with st.spinner("Writing the simple and developer explanations…"):
                st.session_state["explanation"] = explain_report(report, Path(repo_text))
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    if benchmark_clicked:
        try:
            with st.spinner("Running the full suite to measure a real baseline…"):
                baseline = benchmark_full_suite(Path(repo_text), repo_id, head)
            st.session_state["baseline"] = baseline
            st.success(f"Full-suite benchmark: {baseline['duration_seconds']:.2f}s, exit {baseline['exit_code']}.")
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    report = st.session_state.get("result")
    if not report:
        st.divider()
        st.info("Prepare a demo or enter a local repository, then run analysis. Atlas is needed for focused selection; the full suite still runs when it is unavailable.")
        return
    if st.session_state.get("result_context") != context:
        st.warning("Showing the previous run. Repository settings have changed; run analysis to update results.")
    st.divider()
    metrics = dashboard_metrics(report, st.session_state.get("baseline"))
    cards = st.columns(5)
    cards[0].metric("Passed", metrics["passed"])
    cards[1].metric("Failed / errors", metrics["failed"])
    cards[2].metric("Selected / full", f"{report['selected_test_count']} / {report['full_suite_count'] if report['full_suite_count'] is not None else '?'}")
    cards[3].metric("Fewer test cases", f"{metrics['test_reduction']:.0f}%" if metrics["test_reduction"] is not None else "Unknown")
    saved = metrics["time_saved"]
    cards[4].metric("Measured time saved", f"{saved:.2f}s" if saved is not None else "Not measured")
    st.caption(f"Analysis: {report['duration_seconds']:.2f}s · pytest: {report['test_duration_seconds']:.2f}s · skipped: {metrics['skipped']}. "
               "Time saved compares full-suite wall time with total analysis wall time at the same commit; negative means the agent was slower.")
    status = report["test_status"]
    if status == "passed":
        st.success("The executed tests passed.")
    elif status == "failed":
        st.error("The executed tests found a failure.")
    else:
        st.warning("Analysis needs attention: " + status.replace("_", " "))
    if report["fallback"]["ran"]:
        st.warning("Full-suite fallback · " + ", ".join(report["fallback"]["reasons"]))
    if report["persistence"]["status"] != "saved":
        st.info("Shared run memory: " + report["persistence"]["status"])
    if report.get("missed_test_audit", {}).get("missed_failures"):
        st.error("The full-suite audit found additional failures in omitted tests; the failure count includes these audit findings.")
    explanation = st.session_state.get("explanation") or explain_report(report, generate=lambda _: "")
    st.subheader("Why the agent made this decision")
    style = st.radio("Explanation style", ["Simple", "Developer"], horizontal=True, key="explanation_style", index=0)
    st.caption(("Gemini · " if explanation["source"] == "gemini" else "Template · ") + explanation["notice"])
    st.markdown(explanation["simple" if style == "Simple" else "developer"])
    evidence, outcomes, raw = st.tabs(["Selection evidence", "Test results", "Reports & logs"])
    with evidence:
        st.write("Changed files", report["changed_paths"])
        for test in report["selected_tests"]:
            with st.expander(test["test_id"]):
                st.json(test["reasons"])
    with outcomes:
        st.dataframe([{"Test": o["test_id"], "Outcome": o["outcome"], "Seconds": round(o.get("duration_seconds", 0), 3)}
                      for o in report["test_outcomes"]], use_container_width=True)
        for field in ("errors", "collection_errors", "execution_errors"):
            for error in report.get(field, []):
                st.error(error)
    with raw:
        st.download_button("Download JSON", json.dumps(report, indent=2), "impact-report.json", "application/json")
        st.download_button("Download Markdown", st.session_state.get("summary", ""), "impact-summary.md", "text/markdown")
        st.code(st.session_state.get("action_log", ""), language="text")
        st.code(report.get("pytest_output", ""), language="text")
        st.json(report)
