"""JSON and Actions-friendly Markdown reports, including failed runs."""

import html
import json
from pathlib import Path

from .models import Document


def _cell(value) -> str:
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", "<br>")


def _reason(reason: Document) -> str:
    kind = reason["kind"]
    if kind == "graph":
        edges = reason["edges"]
        path = [edges[0]["source_path"]] + [e["target_path"] for e in edges] if edges else []
        return "graph: " + " → ".join(path)
    if kind == "semantic_match":
        return f"semantic match to {reason['changed_path']} ({reason['symbol']}, score {reason['score']:.3f})"
    if kind == "prior_regression":
        return f"failed in similar run {reason['run_id']} (score {reason['score']:.3f})"
    if kind == "changed_test":
        return "changed test: " + reason["changed_path"]
    return "full-suite fallback: " + ", ".join(reason.get("reasons", []))


def write_reports(report: Document, output: Path, summary: Path) -> None:
    if output.resolve() == summary.resolve():
        raise ValueError("JSON and Markdown reports must have different paths.")
    for path in (output, summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    lines = ["# TestEcho", "", f"**Test result:** {_cell(report['test_status'])} (exit {report['exit_code']})",
             "", f"Base: `{_cell(report['base_sha'])}`  ", f"Head: `{_cell(report['head_sha'])}`", "",
             f"Changed paths: {_cell(', '.join(report['changed_paths']) or '(none)')}", "",
             f"Full-suite fallback: **{'yes' if report['fallback']['ran'] else 'no'}**"]
    if report["fallback"]["reasons"]:
        lines.append("Reasons: " + _cell(", ".join(report["fallback"]["reasons"])))
    full_count = report["full_suite_count"]
    lines += ["", f"Selected cases: {report['selected_test_count']}; full-suite cases: {full_count if full_count is not None else 'unknown'}.",
              f"Elapsed: {report['duration_seconds']:.3f}s; pytest: {report['test_duration_seconds']:.3f}s.",
              "", "## Test plan", "", "| Test | Evidence |", "| --- | --- |"]
    for test in report["selected_tests"]:
        lines.append(f"| {_cell(test['test_id'])} | {_cell('; '.join(_reason(r) for r in test['reasons']))} |")
    lines += ["", "## Outcomes", "", "| Test | Outcome | Seconds |", "| --- | --- | --- |"]
    for outcome in report["test_outcomes"]:
        lines.append(f"| {_cell(outcome['test_id'])} | {_cell(outcome['outcome'])} | {outcome['duration_seconds']:.3f} |")
    if audit := report.get("missed_test_audit"):
        lines += ["", "## Missed-test audit", "", f"Status: **{audit['status']}**."]
        for miss in audit["missed_failures"]:
            lines.append(f"- {_cell(miss['test_id'])} failed outside the focused plan.")
    lines += ["", f"Run memory: **{_cell(report['persistence']['status'])}**."]
    if report["persistence"].get("warning"):
        lines.append(_cell(report["persistence"]["warning"]))
    for error in report["errors"] + report["collection_errors"] + report["execution_errors"]:
        lines += ["", "Error: " + _cell(error)]
    if report.get("pytest_output"):
        lines += ["", "<details><summary>Pytest output</summary>", "", "<pre>" + html.escape(report["pytest_output"]) + "</pre>", "", "</details>"]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
