from impact_agent.runner import collect_tests, run_tests, validate_checkout
from impact_agent.gitrepo import GitError

import pytest


def test_selective_execution_expands_parameterized_cases_and_records_failure(git_repo):
    repo, commit = git_repo
    commit({"test_app.py": "import pytest\n@pytest.mark.parametrize('x', [1, 2])\ndef test_value(x):\n    assert x == 1\n\ndef test_other():\n    assert False\n"})
    collection = collect_tests(repo)
    assert collection.exit_code == 0 and len(collection.collected_ids) == 3
    run = run_tests(repo, ["test_app.py::test_value"])
    assert run.exit_code == 1
    assert {r["test_id"]: r["outcome"] for r in run.outcomes} == {
        "test_app.py::test_value[1]": "passed", "test_app.py::test_value[2]": "failed"}
    assert run.duration_seconds > 0


def test_full_suite_records_setup_errors_and_skips(git_repo):
    repo, commit = git_repo
    commit({"test_app.py": "import pytest\n@pytest.fixture\ndef broken():\n    raise RuntimeError('fixture failed')\ndef test_setup(broken):\n    pass\n@pytest.mark.skip(reason='demo')\ndef test_skip():\n    pass\n"})
    run = run_tests(repo)
    assert run.exit_code == 1
    assert {r["test_id"]: r["outcome"] for r in run.outcomes} == {
        "test_app.py::test_setup": "error", "test_app.py::test_skip": "skipped"}
    assert "fixture failed" in run.outcomes[0]["details"]


def test_collection_failure_and_empty_suite_are_nonzero(git_repo):
    repo, commit = git_repo
    commit({"test_broken.py": "def broken(\n"})
    run = run_tests(repo)
    assert run.exit_code != 0 and run.errors
    (repo / "test_broken.py").unlink()
    empty = run_tests(repo)
    assert empty.exit_code == 5


def test_timeout_is_a_failure(git_repo):
    repo, commit = git_repo
    commit({"test_slow.py": "import time\ndef test_slow():\n    time.sleep(10)\n"})
    run = run_tests(repo, timeout=0.3)
    assert run.exit_code == 124 and "timeout" in run.errors[0]


def test_empty_selected_list_never_silently_runs_full_suite(git_repo):
    repo, _ = git_repo
    with pytest.raises(ValueError):
        run_tests(repo, [])


def test_checkout_must_match_head_and_be_clean(git_repo):
    repo, commit = git_repo
    base = commit({"app.py": "VALUE = 1\n"})
    head = commit({"app.py": "VALUE = 2\n"})
    validate_checkout(repo, head)
    with pytest.raises(GitError, match="head"):
        validate_checkout(repo, base)
    (repo / "app.py").write_text("VALUE = 3\n")
    with pytest.raises(GitError, match="tracked"):
        validate_checkout(repo, head)


def test_untracked_python_is_not_part_of_requested_commit(git_repo):
    repo, commit = git_repo
    head = commit({"app.py": "VALUE = 1\n"})
    (repo / "test_untracked.py").write_text("def test_extra():\n    pass\n")
    with pytest.raises(GitError, match="untracked Python"):
        validate_checkout(repo, head)


def test_early_successful_pytest_exit_is_not_a_passing_test_run(git_repo):
    repo, commit = git_repo
    commit({"test_app.py": "import pytest\ndef test_app():\n    pytest.exit('stop early', returncode=0)\n"})
    run = run_tests(repo)
    assert run.exit_code != 0
    assert "incomplete_test_execution" in run.errors


def test_failed_outcome_cannot_be_overridden_by_successful_session_status(git_repo):
    repo, commit = git_repo
    commit({"conftest.py": "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n",
            "test_app.py": "def test_app():\n    assert False\n"})
    run = run_tests(repo)
    assert run.exit_code == 1
    assert run.outcomes[0]["outcome"] == "failed"
