"""AGENT-1/2 orchestration: selection, execution, run memory, and reports."""

from datetime import datetime, timezone
from pathlib import Path
import time
import uuid

from pymongo.errors import PyMongoError

from .gitrepo import GitError, changed_paths, git, resolve_commit, tree_files
from .graph import GraphStore, analyze_graph
from .models import Document, GraphImpact
from .reporting import write_reports
from .runner import collect_tests, run_tests, validate_checkout
from .selection import RetrievalStore, assemble_plan


def _matches(candidate: str, collected: str) -> bool:
    return (candidate == collected or collected.startswith(candidate + "[")
            or collected.startswith(candidate + "::"))


def _run_document(report: Document) -> Document:
    failed = [o["test_id"] for o in report["test_outcomes"] if o["outcome"] in ("failed", "error")]
    summary = "Changed paths: " + ", ".join(report["changed_paths"])
    summary += "; test result: " + report["test_status"] + "; failed tests: " + ", ".join(failed)
    return {
        "_id": report["run_id"], "repo_id": report["repo_id"], "base_sha": report["base_sha"],
        "head_sha": report["head_sha"], "kind": "pr_run", "path": "", "symbol": report["run_id"],
        "search_text": summary, "change_summary": summary, "created_at": report["created_at"],
        "changed_paths": report["changed_paths"], "selected_test_ids": [t["test_id"] for t in report["selected_tests"]],
        "selection_evidence": report["selected_tests"], "test_outcomes": report["test_outcomes"],
        "fallback": report["fallback"], "test_status": report["test_status"],
        "exit_code": report["exit_code"], "duration_seconds": report["duration_seconds"],
    }


def analyze_repository(repo: Path, repo_id: str, base: str, head: str, output: Path, summary: Path,
                       graph_store: GraphStore | None, retrieval: RetrievalStore | None,
                       *, timeout: float = 300) -> Document:
    started = time.monotonic()
    repo, output, summary = repo.resolve(), output.resolve(), summary.resolve()
    if output == summary:
        raise ValueError("JSON and Markdown reports must have different paths.")
    try:
        tracked = {repo / p.decode("utf-8", "surrogateescape")
                   for p in git(repo, "ls-files", "--cached", "-z").split(b"\0") if p}
    except GitError:
        tracked = set()
    if output in tracked or summary in tracked:
        raise ValueError("Report paths must not overwrite tracked repository files.")
    if any((repo / ".git") == path or (repo / ".git") in path.parents for path in (output, summary)):
        raise ValueError("Report paths must not write Git metadata.")
    report = {
        "schema_version": 1, "run_id": uuid.uuid4().hex, "repo_id": repo_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "base_sha": base, "head_sha": head,
        "changed_paths": [], "planned_candidates": [], "selected_tests": [], "test_outcomes": [],
        "fallback": {"ran": False, "reasons": []}, "full_suite_count": None,
        "selected_test_count": 0, "test_status": "not_run", "exit_code": 2,
        "duration_seconds": 0.0, "test_duration_seconds": 0.0, "collection_duration_seconds": 0.0,
        "errors": [], "collection_errors": [], "execution_errors": [],
        "persistence": {"status": "not_attempted"}, "pytest_output": "",
    }
    try:
        base_sha, head_sha = resolve_commit(repo, base), resolve_commit(repo, head)
        report.update(base_sha=base_sha, head_sha=head_sha,
                      changed_paths=changed_paths(repo, base_sha, head_sha))
        # Never overwrite tracked application files with report artifacts.
        tracked = {repo / p for p in tree_files(repo, head_sha, regular_only=False)}
        if output in tracked or summary in tracked:
            raise ValueError("Report paths must not overwrite tracked repository files.")
        validate_checkout(repo, head_sha)
        if graph_store is None:
            impact = GraphImpact(repo_id, base_sha, head_sha, changed_paths=report["changed_paths"],
                                 fallback_reasons=["atlas_unavailable"])
        else:
            impact = analyze_graph(repo, repo_id, base_sha, head_sha, graph_store)
        if retrieval is None and "atlas_unavailable" not in impact.fallback_reasons:
            impact.fallback_reasons.append("atlas_unavailable")
        plan = assemble_plan(impact, retrieval)
        report["planned_candidates"] = plan.candidates
        collection = collect_tests(repo, timeout=min(60, timeout))
        report["collection_duration_seconds"] = collection.duration_seconds
        report["collection_errors"] = collection.errors
        if collection.exit_code == 0:
            report["full_suite_count"] = len(collection.collected_ids)
            if any(not any(_matches(c["test_id"], node) for node in collection.collected_ids)
                   for c in plan.candidates):
                plan.fallback_reasons.append("candidate_not_collected")
        else:
            plan.fallback_reasons.append("pytest_collection_failed")
        report["fallback"] = {"ran": plan.full_suite, "reasons": list(dict.fromkeys(plan.fallback_reasons))}
        report["selected_tests"] = ([{"test_id": node, "reasons": [{"kind": "full_suite", "reasons": plan.fallback_reasons}]}
                                     for node in collection.collected_ids] if plan.full_suite else plan.candidates)
        # Collection executes imports/hooks; make sure it did not alter tracked code.
        validate_checkout(repo, head_sha)
        execution = run_tests(repo, None if plan.full_suite else [c["test_id"] for c in plan.candidates], timeout)
        expected = set(collection.collected_ids) if plan.full_suite else {
            node for node in collection.collected_ids if any(_matches(c["test_id"], node) for c in plan.candidates)
        }
        if collection.exit_code == 0 and set(execution.collected_ids) != expected:
            execution.errors.append("pytest_selection_mismatch")
            if execution.exit_code == 0:
                execution.exit_code = 2
        report.update(test_outcomes=execution.outcomes, execution_errors=execution.errors,
                      selected_test_count=len(execution.collected_ids),
                      test_duration_seconds=execution.duration_seconds, pytest_output=execution.stdout[-20000:])
        report["exit_code"] = execution.exit_code if execution.exit_code >= 0 else 2
        report["test_status"] = "passed" if execution.exit_code == 0 else "failed" if execution.exit_code == 1 else "error"
        if plan.full_suite and report["full_suite_count"] is None:
            report["selected_tests"] = [{"test_id": node, "reasons": [{"kind": "full_suite", "reasons": plan.fallback_reasons}]}
                                         for node in execution.collected_ids]
        report["duration_seconds"] = time.monotonic() - started
        if retrieval is None:
            report["persistence"] = {"status": "unavailable", "warning": "Run memory was not saved because Atlas is unavailable."}
        else:
            try:
                retrieval.save_run(_run_document(report))
                report["persistence"] = {"status": "saved"}
            except PyMongoError:
                report["persistence"] = {"status": "failed", "warning": "Atlas run persistence failed; this run will not inform future selections."}
    except GitError as exc:
        report["errors"].append(str(exc))
    except OSError:
        report["errors"].append("Unable to start or record pytest; check the interpreter and file permissions.")
    report["duration_seconds"] = time.monotonic() - started
    write_reports(report, output, summary)
    return report
