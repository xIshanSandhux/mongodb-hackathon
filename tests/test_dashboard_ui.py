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
    app.button(key="prepare").click().run()
    assert not app.exception and app.text_input(key="repo_path").value
    app.button(key="analyze").click().run(timeout=30)
    assert not app.exception
    assert app.radio(key="explanation_style").value == "Simple"
    report_id = app.session_state["result"]["run_id"]
    app.radio(key="explanation_style").set_value("Developer").run()
    assert not app.exception
    assert app.session_state["result"]["run_id"] == report_id
    assert any(metric.label == "Passed" for metric in app.metric)
