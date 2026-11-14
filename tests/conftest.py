import subprocess

import pytest


@pytest.fixture
def git_repo(tmp_path):
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(tmp_path), *args], text=True
        ).strip()

    git("init", "-q")
    git("config", "user.email", "fixture@example.test")
    git("config", "user.name", "Test Fixture")

    def commit(files):
        for name, text in files.items():
            path = tmp_path / name
            if text is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
        git("add", "-A")
        git("commit", "-qm", "fixture")
        return git("rev-parse", "HEAD")

    return tmp_path, commit
