from contextlib import contextmanager
import json

from typer.testing import CliRunner
from pymongo.errors import OperationFailure

from impact_agent import cli


def test_index_command_persists_requested_snapshot(git_repo, monkeypatch):
    repo, commit = git_repo
    sha = commit({"app.py": "VALUE = 1\n"})
    saved = []
    events = []
    database = object()

    class Client:
        def __enter__(self):
            events.append("connect")
            return self

        def __exit__(self, *exc_info):
            events.append("close")

    class Store:
        def __init__(self, db):
            assert db is database
            events.append("store")

        def save_snapshot(self, snapshot):
            events.append("save")
            saved.append(snapshot)

    monkeypatch.setattr(cli, "create_atlas_client", lambda: Client())
    monkeypatch.setattr(cli, "atlas_database", lambda client: database)
    monkeypatch.setattr(cli, "setup_atlas", lambda db: events.append("setup"))
    monkeypatch.setattr(cli, "AtlasGraphStore", Store)
    result = CliRunner().invoke(cli.app, ["index", "--repo", str(repo), "--repo-id", "demo", "--commit", sha])
    assert result.exit_code == 0, result.output
    assert saved[0].base_sha == sha
    assert saved[0].nodes[0]["path"] == "app.py"
    assert events == ["connect", "setup", "store", "save", "close"]
    assert "Indexed" in result.output


def test_index_failure_does_not_print_database_credentials(git_repo, monkeypatch):
    repo, commit = git_repo
    sha = commit({"app.py": "VALUE = 1\n"})

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(cli, "create_atlas_client", lambda: Client())
    monkeypatch.setattr(cli, "atlas_database", lambda client: object())

    def fail_setup(db):
        raise OperationFailure("mongodb://user:supersecret@host/")

    monkeypatch.setattr(cli, "setup_atlas", fail_setup)
    result = CliRunner().invoke(cli.app, ["index", "--repo", str(repo), "--repo-id", "demo", "--commit", sha])
    assert result.exit_code != 0
    assert "supersecret" not in result.output
    assert "Atlas" in result.output


def test_index_requires_environment_credentials(git_repo, monkeypatch, tmp_path):
    repo, commit = git_repo
    sha = commit({"app.py": "VALUE = 1\n"})
    monkeypatch.delenv("MONGODB_URI", raising=False)
    # The Atlas helper searches for a project .env; do not read a developer's real credentials.
    monkeypatch.setattr("impact_agent.atlas.load_dotenv", lambda: False)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["index", "--repo", str(repo), "--repo-id", "demo", "--commit", sha])
    assert result.exit_code == 2
    assert "MONGODB_URI" in result.output


def test_analyze_without_credentials_runs_full_suite_and_writes_reports(git_repo, monkeypatch, tmp_path):
    repo, commit = git_repo
    base = commit({"app.py": "VALUE = 1\n", "test_app.py": "def test_app():\n    pass\n"})
    head = commit({"app.py": "VALUE = 2\n"})
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.chdir(tmp_path)
    output, summary = tmp_path / "report.json", tmp_path / "summary.md"
    result = CliRunner().invoke(cli.app, ["analyze", "--repo", str(repo), "--repo-id", "demo",
        "--base", base, "--head", head, "--output", str(output), "--summary", str(summary)])
    assert result.exit_code == 0, result.output
    report = json.loads(output.read_text())
    assert report["fallback"]["ran"] and report["test_status"] == "passed"
    assert report["selected_test_count"] == 1
    assert "unavailable" in summary.read_text()


def test_analyze_test_failure_is_a_failing_cli_status(git_repo, monkeypatch, tmp_path):
    repo, commit = git_repo
    base = commit({"app.py": "VALUE = 1\n", "test_app.py": "def test_app():\n    assert False\n"})
    head = commit({"app.py": "VALUE = 2\n"})
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.chdir(tmp_path)
    output, summary = tmp_path / "report.json", tmp_path / "summary.md"
    result = CliRunner().invoke(cli.app, ["analyze", "--repo", str(repo), "--repo-id", "demo",
        "--base", base, "--head", head, "--output", str(output), "--summary", str(summary)])
    assert result.exit_code == 1
    assert json.loads(output.read_text())["test_status"] == "failed" and summary.exists()


def test_analyze_invokes_agent_once(monkeypatch):
    calls = []

    @contextmanager
    def unavailable():
        raise ValueError("no credentials")
        yield

    def analyze_once(*args, **kwargs):
        calls.append(args)
        return {"test_status": "passed", "selected_test_count": 1, "fallback": {"ran": True},
                "persistence": {"status": "saved"}, "exit_code": 0}

    monkeypatch.setattr(cli, "graph_store_from_env", unavailable)
    monkeypatch.setattr(cli, "analyze_repository", analyze_once)
    result = CliRunner().invoke(cli.app, ["analyze", "--repo-id", "demo", "--base", "base", "--head", "head"])
    assert result.exit_code == 0 and len(calls) == 1
