"""TestEcho: compact Streamlit pages over the deterministic agent CLI."""

import json
import os
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from .dashboard_service import SCENARIOS, analyze_local, benchmark_full_suite, dashboard_metrics, index_local, prepare_demo
from .explanations import explain_report
from .payflow_demo import PAYFLOW_SCENARIOS, prepare_payflow_demo


def _go(page):
    st.switch_page(st.session_state["pages"][page])


def _back():
    if st.button("← Results", key="back_results"):
        _go("Results")


def _config():
    return st.session_state["configuration"]


def _context(config):
    return tuple(config[k].strip() for k in ("repo_path", "repo_id", "base", "head"))


def _ready():
    return all(_context(_config()))


def _set_config(config):
    st.session_state["configuration"] = config
    for key in ("result", "explanation", "baseline", "summary", "action_log", "knowledge_notice"):
        st.session_state.pop(key, None)


def _require_config():
    if _ready():
        return True
    st.info("Choose a repository and change first.")
    if st.button("Choose a change", key="need_setup"):
        _go("Setup")
    return False


def _require_report():
    report = st.session_state.get("result")
    if report:
        if st.session_state.get("result_context") != _context(_config()):
            st.warning("These results belong to the previous change. Run the current change to update them.")
        return report
    st.info("Run a change to see its results.")
    if st.button("Continue to run", key="need_run"):
        _go("Run" if _ready() else "Setup")
    return None


def _change_card():
    config = _config()
    with st.container(border=True):
        st.write("**" + config.get("label", "Local change") + "**")
        st.caption(f"{Path(config['repo_path']).name} · {config['base'][:10]} → {config['head'][:10]}")
        if config.get("source_url"):
            st.caption(("Local replay on pinned source" if config.get("generated_change") else "Original upstream commit replay")
                       + f" · [PayFlow repository]({config['source_url']})")


def _setup():
    st.header("Choose a change.")
    st.caption("Start with a prepared demo, or use your own local checkout.")
    mode = st.radio("Repository", ["Prepared demo", "Local repository"], horizontal=True, key="repository_mode")
    if mode == "Prepared demo":
        demo_app = st.selectbox("Demo application", ["PayFlow payments", "Small starter"], key="demo_app")
        scenario = st.selectbox("Demo scenario", PAYFLOW_SCENARIOS if demo_app == "PayFlow payments" else SCENARIOS)
        descriptions = {
            "Focused change": "A pricing change that preserves behavior. See which checks TestEcho chooses.",
            "Regression": "A pricing bug with a real failing test. Watch the failure appear in the report.",
            "Unmapped file fallback": "A new Python file with no base mapping. TestEcho should run the whole suite.",
            "Gateway validation refactor": "A behavior-preserving refactor in the real PayFlow gateway. Uses its actual test suite.",
            "Gateway regression": "A deliberate local precision-validation bug in PayFlow. Its real tests should catch it.",
            "Vendor PR replay": "Replay the original vendor-metadata commits from PayFlow's repository, including its new regression test.",
        }
        st.info(descriptions[scenario])
        if st.button("Prepare & continue →", key="prepare", type="primary", use_container_width=True):
            try:
                with st.spinner("Preparing a separate demo repository…"):
                    demo = prepare_payflow_demo(scenario) if demo_app == "PayFlow payments" else prepare_demo(scenario)
                _set_config({"repo_path": str(demo.repo), "repo_id": demo.repo_id,
                             "base": demo.base, "head": demo.head, "label": demo_app + " · " + scenario,
                             "source_url": demo.source_url, "generated_change": demo.generated_change})
                _go("Knowledge")
            except (ValueError, OSError, RuntimeError) as exc:
                st.error("Could not prepare the demo. " + str(exc))
        if _ready() and st.button("Continue with configured change →", key="continue_configured", use_container_width=True):
            _go("Knowledge")
    else:
        config = _config()
        with st.form("local_repository"):
            repo_path = st.text_input("Repository path", value=config["repo_path"])
            repo_id = st.text_input("Repository ID", value=config["repo_id"])
            left, right = st.columns(2)
            base = left.text_input("Base commit", value=config["base"])
            head = right.text_input("Head commit", value=config["head"])
            submitted = st.form_submit_button("Continue →", type="primary", use_container_width=True)
        if submitted:
            if not all(value.strip() for value in (repo_path, repo_id, base, head)):
                st.error("Fill in the repository and both commits.")
            else:
                _set_config({"repo_path": repo_path.strip(), "repo_id": repo_id.strip(),
                             "base": base.strip(), "head": head.strip(), "label": "Local change"})
                _go("Knowledge")


def _knowledge():
    st.header("Give the change context.")
    if not _require_config():
        return
    _change_card()
    st.write("Atlas stores the code and test relationships that help TestEcho choose relevant checks.")
    st.caption("Already indexed this base? Continue with existing knowledge. Missing or unavailable knowledge triggers the full suite.")
    config = _config()
    if st.button("Index base in Atlas →", key="index", type="primary", use_container_width=True):
        try:
            with st.spinner("Building the committed code and test map…"):
                index_local(Path(config["repo_path"]), config["repo_id"], config["base"])
            st.session_state["knowledge_notice"] = "Base snapshot indexed. Search embeddings may still be building."
            _go("Run")
        except (RuntimeError, OSError) as exc:
            st.error(str(exc))
    if st.button("Continue with existing knowledge →", key="skip_index", use_container_width=True):
        _go("Run")
    if st.button("← Choose another change", key="back_setup"):
        _go("Setup")


def _run():
    st.header("Ready to listen for regressions.")
    if not _require_config():
        return
    _change_card()
    if st.session_state.get("knowledge_notice"):
        st.success(st.session_state["knowledge_notice"])
    st.write("TestEcho will trace this change, choose tests from recorded evidence, and run them.")
    st.caption("Your checkout must already be clean and at the head commit. Uncertainty triggers the full suite. Gemini explains the recorded decisions afterward.")
    if st.button("Run TestEcho →", key="analyze", type="primary", use_container_width=True):
        config = _config()
        try:
            with st.spinner("Selecting and running tests…"):
                report, summary, log = analyze_local(Path(config["repo_path"]), config["repo_id"], config["base"], config["head"])
            st.session_state.update(result=report, summary=summary, action_log=log, result_context=_context(config))
            with st.spinner("Explaining the recorded decisions…"):
                st.session_state["explanation"] = explain_report(report, Path(config["repo_path"]))
            st.session_state["explanation_style"] = "Simple"
            _go("Results")
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    if st.button("← Knowledge settings", key="back_knowledge"):
        _go("Knowledge")


def _results():
    st.header("Your change, checked.")
    report = _require_report()
    if not report:
        return
    metrics = dashboard_metrics(report, st.session_state.get("baseline"))
    columns = st.columns(4)
    columns[0].metric("Passed", metrics["passed"])
    columns[1].metric("Failed / errors", metrics["failed"])
    columns[2].metric("Selected / full", f"{report['selected_test_count']} / {report['full_suite_count'] if report['full_suite_count'] is not None else '?'}")
    saved = metrics["time_saved"]
    columns[3].metric("Time saved", f"{saved:.2f}s" if saved is not None else "Not measured")
    reduction = f"{metrics['test_reduction']:.0f}% fewer cases" if metrics["test_reduction"] is not None else "Case reduction unknown"
    st.caption(f"{reduction} · Analysis {report['duration_seconds']:.2f}s · Memory: {report['persistence']['status']}")
    if report["test_status"] == "passed":
        st.success("The executed tests passed.")
    elif report["test_status"] == "failed":
        st.error("The executed tests found a failure.")
    else:
        st.warning("Analysis needs attention: " + report["test_status"].replace("_", " "))
    if report["fallback"]["ran"]:
        st.warning("Full-suite fallback · " + ", ".join(report["fallback"]["reasons"]))
    if report.get("missed_test_audit", {}).get("missed_failures"):
        st.error("The count includes additional failures found by the full-suite audit.")
    left, right = st.columns(2)
    if left.button("Why these tests? →", key="show_explanation", type="primary", use_container_width=True):
        _go("Explanation")
    if right.button("See test results →", key="show_tests", use_container_width=True):
        _go("Tests")
    if left.button("Measure timing →", key="show_timing", use_container_width=True):
        _go("Timing")
    if right.button("Reports & logs →", key="show_reports", use_container_width=True):
        _go("Reports")


def _explanation():
    st.header("Why these tests?")
    report = _require_report()
    if not report:
        return
    explanation = st.session_state.get("explanation") or explain_report(report, generate=lambda _: "")
    style = st.radio("Explanation style", ["Simple", "Developer"], horizontal=True, key="explanation_style")
    st.caption(("Gemini · " if explanation["source"] == "gemini" else "Template · ") + explanation["notice"])
    with st.container(height=300, border=True):
        st.markdown(explanation["simple" if style == "Simple" else "developer"])
    _back()


def _tests():
    st.header("Tests and evidence.")
    report = _require_report()
    if not report:
        return
    view = st.radio("Inspect", ["Outcomes", "Selection evidence", "Analysis errors"], horizontal=True)
    with st.container(height=320, border=True):
        if view == "Outcomes":
            outcomes = report["test_outcomes"] + report.get("missed_test_audit", {}).get("missed_failures", [])
            st.dataframe([{"Test": o["test_id"], "Outcome": o["outcome"], "Seconds": round(o.get("duration_seconds", 0), 3)}
                          for o in outcomes], use_container_width=True, height=260)
        elif view == "Selection evidence":
            tests = report["selected_tests"]
            if tests:
                selected = st.selectbox("Selected test", range(len(tests)), format_func=lambda i: tests[i]["test_id"])
                st.json(tests[selected]["reasons"])
            else:
                st.info("No tests were selected.")
        else:
            errors = report.get("errors", []) + report.get("collection_errors", []) + report.get("execution_errors", [])
            st.code("\n\n".join(errors) or "No analysis errors recorded.", language="text")
    _back()


def _timing():
    st.header("Measure, don't guess.")
    report = _require_report()
    if not report:
        return
    st.metric("Total analysis", f"{report['duration_seconds']:.2f}s")
    st.write("Run the full suite at the same commit for a real comparison.")
    st.caption("Time saved includes retrieval and collection overhead. Negative savings mean the agent was slower. This is a local observation, not a performance guarantee.")
    if st.button("Measure full suite →", key="benchmark", type="primary", use_container_width=True):
        config = _config()
        try:
            with st.spinner("Running the full suite…"):
                baseline = benchmark_full_suite(Path(config["repo_path"]), config["repo_id"], config["head"])
            st.session_state["baseline"] = baseline
            _go("Results")
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    _back()


def _reports():
    st.header("Take the evidence with you.")
    report = _require_report()
    if not report:
        return
    left, right = st.columns(2)
    left.download_button("Download JSON", json.dumps(report, indent=2), "testecho-report.json", "application/json", use_container_width=True)
    right.download_button("Download Markdown", st.session_state.get("summary", ""), "testecho-summary.md", "text/markdown", use_container_width=True)
    view = st.radio("Preview", ["Summary", "Pytest log", "Agent log", "Raw JSON"], horizontal=True)
    with st.container(height=270, border=True):
        if view == "Summary":
            st.markdown(st.session_state.get("summary", ""))
        elif view == "Pytest log":
            st.code(report.get("pytest_output", ""), language="text")
        elif view == "Agent log":
            st.code(st.session_state.get("action_log", ""), language="text")
        else:
            st.json(report)
    _back()


def _render(name, handler):
    st.session_state["current_step"] = name
    handler()


def main():
    load_dotenv(Path.cwd() / ".env", override=False)
    st.set_page_config(page_title="TestEcho", page_icon="◉", layout="wide")
    st.markdown("""<style>
    .block-container {max-width:1080px;padding-top:3.8rem;padding-bottom:1.5rem}
    div[data-testid="stMetric"] {background:#023430;border:1px solid #3D4F58;border-radius:12px;padding:15px}
    h1,h2 {letter-spacing:-1px} h2 {padding-top:0.2rem}
    .testecho-brand {font-size:1.5rem;font-weight:750;color:#FFFFFF;letter-spacing:-.8px;line-height:1.5}
    .testecho-brand .echo {color:#00ED64} .brand-row {display:flex;align-items:center;justify-content:space-between;gap:12px}
    .powered {font-size:.8rem;color:#B8C4C2} div[data-testid="stCaptionContainer"] {color:#B8C4C2}
    button[kind="primary"],button[kind="primary"] p {color:#001E2B!important;background-color:#00ED64!important}
    </style><div class="brand-row"><div class="testecho-brand">◉ Test<span class="echo">Echo</span></div><span class="powered">Powered by MongoDB</span></div>""", unsafe_allow_html=True)
    if "configuration" not in st.session_state:
        st.session_state["configuration"] = {
            "repo_path": os.environ.get("IMPACT_DEMO_REPO", ""), "repo_id": os.environ.get("REPO_ID", "demo-python"),
            "base": os.environ.get("IMPACT_DEMO_BASE", "HEAD^"), "head": os.environ.get("IMPACT_DEMO_HEAD", "HEAD"),
            "label": "Configured change",
        }
    handlers = {"Setup": _setup, "Knowledge": _knowledge, "Run": _run, "Results": _results,
                "Explanation": _explanation, "Tests": _tests, "Timing": _timing, "Reports": _reports}
    pages = {name: st.Page(partial(_render, name, handler), title=name,
                           url_path=name.lower(), default=name == "Setup") for name, handler in handlers.items()}
    st.session_state["pages"] = pages
    navigation = st.navigation({"Workflow": [pages[name] for name in ("Setup", "Knowledge", "Run", "Results")],
                                "Inspect": [pages[name] for name in ("Explanation", "Tests", "Timing", "Reports")]})
    with st.sidebar:
        st.markdown("**TestEcho**")
        st.caption("Powered by MongoDB")
        st.caption("Atlas: " + ("configured" if os.environ.get("MONGODB_URI") else "not configured"))
        st.caption("Explanations: " + ("Gemini" if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") else "templates"))
    navigation.run()
