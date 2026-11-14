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
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["index", "--repo", str(repo), "--repo-id", "demo", "--commit", sha])
    assert result.exit_code == 2
    assert "MONGODB_URI" in result.output
