"""Private subprocess entry point: run pytest with structured outcome recording."""

import json
from pathlib import Path
import sys


class Recorder:
    def __init__(self, destination: Path):
        self.destination = destination
        self.collected_ids = []
        self.outcomes = {}
        self.errors = []

    def pytest_collection_finish(self, session):
        self.collected_ids = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(str(report.longrepr))

    def pytest_runtest_logreport(self, report):
        item = self.outcomes.setdefault(report.nodeid, {
            "test_id": report.nodeid, "outcome": "incomplete", "duration_seconds": 0.0, "details": "",
            "phases": [],
        })
        item["duration_seconds"] += report.duration
        item["phases"].append(report.when)
        if report.failed:
            item["outcome"] = "failed" if report.when == "call" else "error"
            item["details"] += report.longreprtext + "\n"
        elif report.skipped and item["outcome"] in ("passed", "incomplete"):
            item["outcome"] = "skipped"
            item["details"] = str(report.longrepr)
        elif report.when == "call" and report.passed and item["outcome"] == "incomplete":
            item["outcome"] = "passed"

    def pytest_sessionfinish(self, session, exitstatus):
        self.destination.write_text(json.dumps({
            "collected_ids": self.collected_ids,
            "outcomes": list(self.outcomes.values()), "errors": self.errors,
        }), encoding="utf-8")


def main():
    import pytest

    recorder = Recorder(Path(sys.argv[1]))
    return int(pytest.main(sys.argv[2:], plugins=[recorder]))


if __name__ == "__main__":
    raise SystemExit(main())
