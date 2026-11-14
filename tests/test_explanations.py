import json
from unittest.mock import MagicMock

import pytest

from impact_agent.explanations import explain_report, explanation_payload


def report():
    return {"repo_id": "demo", "base_sha": "base", "head_sha": "head", "test_status": "failed", "exit_code": 1,
            "changed_paths": ["app.py"], "selected_test_count": 1, "full_suite_count": 4,
            "duration_seconds": 1.2, "test_duration_seconds": 0.5,
            "fallback": {"ran": False, "reasons": []},
            "selected_tests": [{"test_id": "test_app.py::test_app", "reasons": [{"kind": "changed_test", "changed_path": "test_app.py"}]}],
            "test_outcomes": [{"test_id": "test_app.py::test_app", "outcome": "failed", "details": "assert 2 == 1"}],
            "persistence": {"status": "saved"}, "errors": [], "collection_errors": [], "execution_errors": []}


def test_no_key_produces_both_grounded_fallback_styles(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = explain_report(report())
    assert result["source"] == "template"
    assert "1" in result["simple"] and "failed" in result["simple"]
    assert "test_app.py::test_app" in result["developer"]
    assert "time saved" not in result["simple"].lower()


def test_payload_redacts_keys_and_credentials(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "very-secret-api-value")
    value = report()
    value["test_outcomes"][0]["details"] = "very-secret-api-value mongodb+srv://user:password@host"
    payload = json.dumps(explanation_payload(value))
    assert "very-secret-api-value" not in payload and "password" not in payload
    assert "assert" not in payload


def test_client_generates_both_styles_once_and_invalid_output_falls_back():
    calls = []

    def generate(payload):
        calls.append(payload)
        return '{"simple": "One selected test failed.", "developer": "Changed-test evidence selected test_app.py::test_app."}'

    result = explain_report(report(), generate=generate)
    assert result["source"] == "gemini" and len(calls) == 1
    invalid = explain_report(report(), generate=lambda payload: "not json")
    assert invalid["source"] == "template" and invalid["notice"]


def test_api_error_is_sanitized_and_does_not_change_test_result():
    def fail(payload):
        raise RuntimeError("key=supersecret")

    result = explain_report(report(), generate=fail)
    assert result["source"] == "template" and "supersecret" not in json.dumps(result)
    assert "failed" in result["simple"]


def test_assignment_redaction_preserves_json_structure():
    value = report()
    value["test_outcomes"][0]["details"] = "api_key=topsecret"
    payload = explanation_payload(value)
    assert payload["test_outcomes"][0]["details"] == "api_key=[REDACTED]"


def test_quoted_credentials_are_redacted_in_code_and_logs():
    value = report()
    value["pytest_output"] = '{"password": "hardcoded-sensitive-value", "token": "other-value"}'
    payload = json.dumps(explanation_payload(value))
    assert "hardcoded-sensitive-value" not in payload and "other-value" not in payload


def test_template_explains_failures_from_missed_test_audit(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    value = report()
    value["test_outcomes"][0]["outcome"] = "passed"
    value["missed_test_audit"] = {"status": "completed", "missed_failures": [{"test_id": "test_missed", "outcome": "failed"}]}
    result = explain_report(value)
    assert "audit" in result["simple"] and "test_missed" in result["developer"]


def test_gemini_adapter_bounds_retries_and_requests_both_styles(monkeypatch):
    genai = pytest.importorskip("google.genai")
    from impact_agent.explanations import _generate

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.return_value.text = '{"simple":"Summary","developer":"Evidence"}'
    monkeypatch.setattr(genai, "Client", factory)
    result = _generate({"test_status": "passed"})
    assert factory.call_args.kwargs["http_options"]["retry_options"]["attempts"] == 1
    assert client.models.generate_content.call_count == 1
    assert "developer" in json.loads(result)
