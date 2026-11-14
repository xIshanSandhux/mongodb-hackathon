"""Read Git objects without checking out or executing the demo repository."""

import io
from pathlib import Path
import subprocess
import tokenize


class GitError(ValueError):
    pass


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        # Do not echo Git diagnostics: remotes can contain embedded credentials.
        raise GitError(f"Git {args[0]} failed; verify the repository and requested commits.")
    return result.stdout


def resolve_commit(repo: Path, commit: str) -> str:
    return git(repo, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}").decode().strip()


def tree_files(repo: Path, sha: str, *, regular_only: bool = True) -> dict[str, str]:
    """Return tracked blobs, normally excluding symlinks; never follow them."""
    files = {}
    for entry in git(repo, "ls-tree", "-rz", "--full-tree", sha).split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            if kind == b"blob" and (not regular_only or mode in (b"100644", b"100755")):
                files[name.decode("utf-8", "surrogateescape")] = oid.decode()
    return files


def read_python(repo: Path, oid: str) -> str:
    raw = git(repo, "cat-file", "blob", oid)
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def changed_paths(repo: Path, base: str, head: str) -> list[str]:
    # A rename is deliberately delete+add: a new path is not mapped to the base.
    raw = git(repo, "diff", "--name-only", "--no-renames", "-z", base, head, "--")
    return sorted(p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p)
