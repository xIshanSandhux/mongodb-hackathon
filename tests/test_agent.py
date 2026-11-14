import json
import pytest

from pymongo.errors import ConnectionFailure

from impact_agent.agent import analyze_repository
from impact_agent.indexer import build_snapshot
from test_graph import FixtureStore
from test_selection import Retrieval, test_document


class Memory(Retrieval):
    def __init__(self, tests=(), runs=()):
        super().__init__(tests, runs)
        self.saved = []

    def save_run(self, document):
        self.saved.append(document)


def files(tmp_path):
    return tmp_path / "reports" / "result.json", tmp_path / "reports" / "summary.md"


def demo(git_repo):
    repo, commit = git_repo
    base = commit({"app.py": "VALUE = 1\n", "test_app.py": "from app import VALUE\ndef test_app():\n    assert VALUE == 1\n",
                   "test_other.py": "def test_other():\n    pass\n"})
    head = commit({"app.py": "VALUE = 2\n"})
    return repo, base, head, FixtureStore(build_snapshot(repo, "demo", base))


def test_failed_selected_test_writes_reports_and_persists_memory(git_repo, tmp_path):
    repo, base, head, graph = demo(git_repo)
    memory = Memory()
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, head, output, summary, graph, memory)
    assert report["exit_code"] == 1 and report["test_status"] == "failed"
    assert not report["fallback"]["ran"]
    assert report["full_suite_count"] == 2 and report["selected_test_count"] == 1
    assert report["test_outcomes"][0]["outcome"] == "failed"
    assert json.loads(output.read_text())["base_sha"] == base
    assert "test_app.py::test_app" in summary.read_text() and "failed" in summary.read_text()
    assert memory.saved[0]["kind"] == "pr_run"
    assert memory.saved[0]["changed_paths"] == ["app.py"]
    assert memory.saved[0]["test_outcomes"][0]["outcome"] == "failed"


def test_missing_atlas_runs_full_suite_and_reports_storage_warning(git_repo, tmp_path):
    repo, base, head, _ = demo(git_repo)
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, head, output, summary, None, None)
    assert report["fallback"]["ran"]
    assert report["selected_test_count"] == 2 and report["exit_code"] == 1
    assert report["persistence"]["status"] == "unavailable"
    assert "atlas_unavailable" in report["fallback"]["reasons"]


def test_invalid_candidate_causes_full_suite_instead_of_silent_drop(git_repo, tmp_path):
    repo, base, head, graph = demo(git_repo)
    doc = test_document("test_removed")
    doc["base_sha"] = base
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, head, output, summary, graph, Memory([doc]))
    assert report["fallback"]["ran"]
    assert "candidate_not_collected" in report["fallback"]["reasons"]
    assert report["selected_test_count"] == 2


def test_wrong_checkout_writes_error_reports_without_running_tests(git_repo, tmp_path):
    repo, base, head, graph = demo(git_repo)
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, base, output, summary, graph, Memory())
    assert report["exit_code"] == 2 and report["test_status"] == "not_run"
    assert report["test_outcomes"] == []
    assert output.exists() and summary.exists()


def test_persistence_failure_keeps_test_result_and_reports_warning(git_repo, tmp_path):
    repo, commit = git_repo
    base = commit({"app.py": "VALUE = 1\n", "test_app.py": "import app\ndef test_app():\n    pass\n"})
    head = commit({"app.py": "VALUE = 2\n"})

    class BrokenMemory(Memory):
        def save_run(self, document):
            raise ConnectionFailure("mongodb://secret")

    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, head, output, summary,
                                FixtureStore(build_snapshot(repo, "demo", base)), BrokenMemory())
    assert report["exit_code"] == 0 and report["test_status"] == "passed"
    assert report["persistence"]["status"] == "failed"
    assert "secret" not in output.read_text() + summary.read_text()


def test_reports_survive_invalid_git_input(git_repo, tmp_path):
    repo, commit = git_repo
    head = commit({"test_app.py": "def test_app():\n    pass\n"})
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", "not-a-commit", head, output, summary, None, None)
    assert report["exit_code"] == 2 and output.exists() and summary.exists()


def test_collection_error_still_produces_both_reports(git_repo, tmp_path):
    repo, commit = git_repo
    base = commit({"test_app.py": "def test_app():\n    pass\n"})
    head = commit({"test_app.py": "def broken(\n"})
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, head, output, summary, None, None)
    assert report["exit_code"] != 0 and report["test_status"] == "error"
    assert report["collection_errors"] and report["execution_errors"]
    assert report["full_suite_count"] is None
    assert output.exists() and summary.exists()


def test_saved_failure_can_contribute_to_a_later_change(git_repo, tmp_path_factory):
    repo, commit = git_repo
    base = commit({"app.py": "VALUE = 1\n", "other.py": "VALUE = 1\n",
                   "test_app.py": "from app import VALUE\ndef test_app():\n    assert VALUE == 1\n"})
    first_head = commit({"app.py": "VALUE = 2\n"})

    class RecalledMemory(Memory):
        def search_runs(self, repo_id, text, limit=3):
            return [{**document, "score": 0.9} for document in self.saved][-limit:]

    memory = RecalledMemory()
    output, summary = files(tmp_path_factory.mktemp("memory-reports"))
    first = analyze_repository(repo, "demo", base, first_head, output, summary,
                               FixtureStore(build_snapshot(repo, "demo", base)), memory)
    assert first["test_status"] == "failed" and memory.saved
    second_head = commit({"other.py": "VALUE = 2\n"})
    second = analyze_repository(repo, "demo", first_head, second_head, output, summary,
                                FixtureStore(build_snapshot(repo, "demo", first_head)), memory)
    assert second["selected_tests"][0]["test_id"] == "test_app.py::test_app"
    assert second["selected_tests"][0]["reasons"][0]["kind"] == "prior_regression"
    assert not second["fallback"]["ran"]


def test_invalid_git_input_cannot_overwrite_tracked_files(git_repo, tmp_path):
    repo, commit = git_repo
    sha = commit({"app.py": "VALUE = 1\n"})
    with pytest.raises(ValueError, match="tracked"):
        analyze_repository(repo, "demo", "invalid", sha, repo / "app.py", tmp_path / "summary.md", None, None)
    assert (repo / "app.py").read_text() == "VALUE = 1\n"


def test_runtime_deselection_cannot_hide_a_planned_test(git_repo, tmp_path):
    repo, commit = git_repo
    base = commit({
        "app.py": "VALUE = 1\n",
        "test_app.py": "import app\ndef test_app():\n    pass\ndef test_other():\n    pass\n",
        "conftest.py": "def pytest_collection_modifyitems(config, items):\n    if not config.option.collectonly:\n        items[:] = [i for i in items if i.name != 'test_app']\n",
    })
    head = commit({"app.py": "VALUE = 2\n"})
    output, summary = files(tmp_path)
    report = analyze_repository(repo, "demo", base, head, output, summary,
                                FixtureStore(build_snapshot(repo, "demo", base)), Memory())
    assert report["exit_code"] != 0
    assert "pytest_selection_mismatch" in report["execution_errors"]
