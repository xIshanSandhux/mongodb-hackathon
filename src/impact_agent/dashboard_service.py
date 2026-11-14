"""Local UI actions over the CLI; demo source lives in separate temporary repos."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from .explanations import redact, redact_data
from .gitrepo import git, resolve_commit
from .runner import run_tests, validate_checkout

SCENARIOS = ("Focused change", "Regression", "Unmapped file fallback")


@dataclass
class Demo:
    repo: Path
    repo_id: str
    base: str
    head: str


def prepare_demo(scenario: str, *, parent: Path | None = None) -> Demo:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown demo scenario")
    repo = Path(tempfile.mkdtemp(prefix="impact-demo-", dir=parent))
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Impact Demo")
    git(repo, "config", "user.email", "demo@example.test")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (repo / "pricing.py").write_text("def total(price, quantity):\n    return price * quantity\n", encoding="utf-8")
    (repo / "test_pricing.py").write_text("from pricing import total\ndef test_total():\n    assert total(10, 2) == 20\n", encoding="utf-8")
    (repo / "test_other.py").write_text(
        "import pytest\nimport time\n@pytest.mark.parametrize('value', range(12))\n"
        "def test_unrelated(value):\n    time.sleep(0.03)\n    assert value >= 0\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Demo baseline")
    base = resolve_commit(repo, "HEAD")
    if scenario == "Unmapped file fallback":
        (repo / "new_feature.py").write_text("FEATURE_ENABLED = True\n", encoding="utf-8")
    else:
        body = "price + quantity" if scenario == "Regression" else "sum(price for _ in range(quantity))"
        (repo / "pricing.py").write_text(f"def total(price, quantity):\n    return {body}\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", scenario)
    return Demo(repo, "demo-" + repo.name, base, resolve_commit(repo, "HEAD"))


def _cli(args: list[str], timeout: float = 360):
    try:
        return subprocess.run([sys.executable, "-c", "from impact_agent.cli import app; app()", *args],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("The action timed out. No successful result was assumed.") from None


def index_local(repo: Path, repo_id: str, base: str) -> str:
    result = _cli(["index", "--repo", str(repo), "--repo-id", repo_id, "--commit", base], timeout=90)
    message = redact(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(message or "Indexing failed; check Atlas configuration.")
    return message


def analyze_local(repo: Path, repo_id: str, base: str, head: str):
    folder = Path(tempfile.mkdtemp(prefix="impact-report-"))
    output, summary = folder / "report.json", folder / "summary.md"
    result = _cli(["analyze", "--repo", str(repo), "--repo-id", repo_id, "--base", base, "--head", head,
                   "--output", str(output), "--summary", str(summary)])
    if not output.exists():
        raise RuntimeError(redact(result.stdout + result.stderr) or "Analysis did not produce a report.")
    report = redact_data(json.loads(output.read_text(encoding="utf-8")))
    return report, redact(summary.read_text(encoding="utf-8")), redact(result.stdout + result.stderr)


def benchmark_full_suite(repo: Path, repo_id: str, head: str) -> dict:
    sha = resolve_commit(repo, head)
    validate_checkout(repo, sha)
    result = run_tests(repo)
    return {"repo_id": repo_id, "head_sha": sha, "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds, "case_count": len(result.collected_ids),
            "errors": result.errors}


def dashboard_metrics(report: dict, baseline: dict | None = None) -> dict:
    outcomes = report.get("test_outcomes", [])
    missed = report.get("missed_test_audit", {}).get("missed_failures", [])
    total, selected = report.get("full_suite_count"), report.get("selected_test_count", 0)
    comparable = (baseline is not None and baseline.get("repo_id") == report.get("repo_id")
                  and report.get("test_status") in ("passed", "failed")
                  and baseline.get("head_sha") == report.get("head_sha")
                  and baseline.get("exit_code") in (0, 1) and not baseline.get("errors"))
    return {"passed": sum(o.get("outcome") == "passed" for o in outcomes),
            "failed": sum(o.get("outcome") in ("failed", "error") for o in outcomes + missed),
            "skipped": sum(o.get("outcome") == "skipped" for o in outcomes),
            "test_reduction": max(0, 100 * (1 - selected / total)) if total and report.get("test_status") in ("passed", "failed") else None,
            "time_saved": baseline["duration_seconds"] - report["duration_seconds"] if comparable else None}
