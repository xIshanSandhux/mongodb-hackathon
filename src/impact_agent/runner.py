"""Execute pytest in the head checkout and capture structured subprocess results."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .gitrepo import GitError, git, resolve_commit
from .models import Document


@dataclass
class Execution:
    exit_code: int
    collected_ids: list[str] = field(default_factory=list)
    outcomes: list[Document] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    stdout: str = ""


def validate_checkout(repo: Path, head_sha: str) -> None:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if root != repo.resolve():
        raise GitError("The repository path must be the Git repository root.")
    if resolve_commit(repo, "HEAD") != head_sha:
        raise GitError("The checkout must be at the requested head commit before running tests.")
    if git(repo, "diff", "--name-only", "HEAD", "--").strip():
        raise GitError("The checkout has tracked changes; tests would not represent the requested head.")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    if any(p.endswith(b".py") for p in untracked):
        raise GitError("The checkout has untracked Python files; commit or move them before analysis.")


def _execute(repo: Path, test_ids: list[str] | None, *, collect: bool, timeout: float) -> Execution:
    if test_ids == []:
        raise ValueError("An empty targeted plan cannot run pytest; choose full-suite fallback explicitly.")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="impact-pytest-") as temp:
        destination = Path(temp) / "results.json"
        command = [sys.executable, "-m", "impact_agent.pytest_runner", str(destination),
                   "-q", "-o", "addopts=", "-o", f"cache_dir={temp}/cache"]
        if collect:
            command.append("--collect-only")
        if test_ids:
            command.extend(["--", *test_ids])
        env = os.environ.copy()
        for name in ("MONGODB_URI", "MONGODB_TEST_URI", "PYTEST_ADDOPTS"):
            env.pop(name, None)
        with subprocess.Popen(command, cwd=repo, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                              start_new_session=(os.name == "posix")) as process:
            try:
                stdout, _ = process.communicate(timeout=timeout)
                code, errors = process.returncode, []
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                stdout, _ = process.communicate()
                code, errors = 124, ["pytest_timeout"]
        data = {}
        if destination.exists():
            try:
                data = json.loads(destination.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                errors.append("invalid_pytest_result")
        else:
            errors.append("missing_pytest_result")
        if code == 0 and any(o["outcome"] in ("failed", "error") for o in data.get("outcomes", [])):
            code = 1
        if code == 0 and data.get("errors"):
            code = 2
        if not collect and code == 0 and (
            not data.get("collected_ids")
            or {o["test_id"] for o in data.get("outcomes", [])} != set(data.get("collected_ids", []))
            or any(o["outcome"] == "incomplete" or "teardown" not in o["phases"] for o in data.get("outcomes", []))
        ):
            errors.append("incomplete_test_execution")
        if errors and code == 0:
            code = 2
        return Execution(code, data.get("collected_ids", []), data.get("outcomes", []),
                         errors + data.get("errors", []), time.monotonic() - started, stdout)


def collect_tests(repo: Path, timeout: float = 60) -> Execution:
    return _execute(repo, None, collect=True, timeout=timeout)


def run_tests(repo: Path, test_ids: list[str] | None = None, timeout: float = 300) -> Execution:
    return _execute(repo, test_ids, collect=False, timeout=timeout)
