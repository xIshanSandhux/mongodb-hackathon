"""Pinned PayFlow replays in separate Git roots; never edit or push upstream."""

from pathlib import Path
import subprocess
import tempfile

from .dashboard_service import Demo
from .gitrepo import git, resolve_commit

PAYFLOW_URL = "https://github.com/ash-raf-codes/payment_processing_app"
PAYFLOW_REVISION = "7d80d2eea28b6ee604cdb14781ff5f72303079a6"
PAYFLOW_REPLAY_BASE = "e9b8d83a2b9fc33a95eb152c9e4880d1e7646332"
PAYFLOW_REPLAY_HEAD = "827cc148542f405f517a07e615de74b5a3ce5e47"
PAYFLOW_SCENARIOS = ("Gateway validation refactor", "Gateway regression", "Vendor PR replay")
_PRECISION_CHECK = 'if value != value.quantize(Decimal("0.01")):'


def prepare_payflow_demo(scenario: str, *, source: Path | None = None,
                         revision: str = PAYFLOW_REVISION, parent: Path | None = None) -> Demo:
    if scenario not in PAYFLOW_SCENARIOS:
        raise ValueError("Unknown PayFlow scenario")
    repo = Path(tempfile.mkdtemp(prefix="testecho-payflow-", dir=parent))
    try:
        cloned = subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--", str(source or PAYFLOW_URL), str(repo)],
                                capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise RuntimeError("PayFlow download timed out. Check your connection and try again.") from None
    if cloned.returncode:
        raise RuntimeError("Could not download the pinned PayFlow repository. Check Git and network access.")
    if scenario == "Vendor PR replay":
        git(repo, "checkout", "--quiet", "--detach", PAYFLOW_REPLAY_HEAD)
        return Demo(repo, "payflow-demo", PAYFLOW_REPLAY_BASE, resolve_commit(repo, "HEAD"), PAYFLOW_URL, False)
    git(repo, "checkout", "--quiet", "--detach", revision)
    base = resolve_commit(repo, "HEAD")
    gateway = repo / "app/main.py"
    original = gateway.read_text(encoding="utf-8")
    if original.count(_PRECISION_CHECK) != 1:
        raise RuntimeError("The pinned gateway no longer matches this replay. No source change was applied.")
    replacement = ('if value.quantize(Decimal("0.01")) != value:' if scenario == PAYFLOW_SCENARIOS[0]
                   else 'if False and value != value.quantize(Decimal("0.01")):')
    gateway.write_text(original.replace(_PRECISION_CHECK, replacement), encoding="utf-8")
    git(repo, "config", "user.name", "TestEcho Demo")
    git(repo, "config", "user.email", "demo@example.test")
    git(repo, "add", "app/main.py")
    git(repo, "commit", "-qm", "Local TestEcho replay: " + scenario)
    return Demo(repo, "payflow-demo", base, resolve_commit(repo, "HEAD"), PAYFLOW_URL, True)
