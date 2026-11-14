from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_dashboard_prepares_and_runs_demo_with_simple_default(monkeypatch, tmp_path):
    # Keep developer .env credentials out of deterministic UI tests and CLI children.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert any("TestEcho" in item.value for item in app.markdown)
    app.button(key="prepare").click().run()
    assert not app.exception and app.session_state["configuration"]["repo_path"]
    assert app.session_state["current_step"] == "Knowledge"
    app.button(key="skip_index").click().run()
    assert app.session_state["current_step"] == "Run"
    app.button(key="analyze").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["current_step"] == "Results"
    assert not app.radio  # The overview does not include explanation or long evidence.
    assert any(metric.label == "Passed" for metric in app.metric)
    app.button(key="show_explanation").click().run()
    assert app.radio(key="explanation_style").value == "Simple"
    report_id = app.session_state["result"]["run_id"]
    app.radio(key="explanation_style").set_value("Developer").run()
    assert not app.exception
    assert app.session_state["result"]["run_id"] == report_id
    app.button(key="back_results").click().run()
    assert app.session_state["current_step"] == "Results"
    assert app.session_state["result"]["run_id"] == report_id
    app.button(key="show_tests").click().run()
    assert app.session_state["current_step"] == "Tests"
    assert app.session_state["result"]["run_id"] == report_id


def test_indexing_advances_to_run_and_configuration_survives_pages(monkeypatch, tmp_path):
    import impact_agent.dashboard as dashboard

    monkeypatch.chdir(tmp_path)
    for key in ("MONGODB_URI", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    calls = []
    monkeypatch.setattr(dashboard, "index_local", lambda *args: calls.append(args))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.button(key="prepare").click().run()
    config = app.session_state["configuration"].copy()
    app.button(key="index").click().run()
    assert not app.exception and app.session_state["current_step"] == "Run"
    assert len(calls) == 1
    app.button(key="back_knowledge").click().run()
    assert app.session_state["configuration"] == config and len(calls) == 1
    assert app.session_state["current_step"] == "Knowledge"
