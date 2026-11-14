"""Compare a full pytest run with the suites reachable from one changed service.

This is a local graph-selection demonstration for the demo app; it is not the
production PR Impact Agent CLI. It makes the full-suite versus focused-suite
cost visible while the agent's selector is being integrated.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.dependency_graph import SERVICE_DEPENDENTS, downstream_services  # noqa: E402


def test_paths_for(services: set[str]) -> list[str]:
    paths = []
    for service in sorted(services):
        if service == "gateway":
            paths.extend(["tests/test_gateway.py", "tests/test_gateway_validation_matrix.py"])
        elif service == "dependency_graph":
            paths.append("tests/test_dependency_graph.py")
        else:
            candidate = f"tests/services/test_{service}.py"
            if (ROOT / candidate).exists():
                paths.append(candidate)
    if "gateway" in services and "tests/test_dependency_graph.py" not in paths:
        paths.append("tests/test_dependency_graph.py")
    return paths


def collect(paths: list[str]) -> int:
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", *paths]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    return sum("::" in line for line in result.stdout.splitlines())


def run(paths: list[str]) -> tuple[float, int]:
    count = collect(paths)
    started = time.perf_counter()
    subprocess.run([sys.executable, "-m", "pytest", "-q", *paths], cwd=ROOT, check=True)
    return time.perf_counter() - started, count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-service", choices=sorted(SERVICE_DEPENDENTS), required=True)
    args = parser.parse_args()
    selected_services = {args.changed_service} | downstream_services(args.changed_service)
    focused_paths = test_paths_for(selected_services)
    full_paths = ["tests"]

    print(f"Changed service: {args.changed_service}")
    print("Graph-selected services:", ", ".join(sorted(selected_services)))
    print("Running full suite...")
    full_seconds, full_count = run(full_paths)
    print("Running graph-selected suite...")
    focused_seconds, focused_count = run(focused_paths)
    saved = full_seconds - focused_seconds
    percent = (saved / full_seconds * 100) if full_seconds else 0
    print("\nComparison (local demo; timings vary by machine)")
    print(f"Full suite:     {full_count:>3} tests, {full_seconds:.3f}s")
    print(f"Graph selected: {focused_count:>3} tests, {focused_seconds:.3f}s")
    print(f"Time saved:     {saved:.3f}s ({percent:.1f}%)")


if __name__ == "__main__":
    main()
