"""Command-line entry point for the PR Impact Agent MVP."""

from pathlib import Path

import typer
from pymongo.errors import PyMongoError

from .gitrepo import GitError
from .graph_store import graph_store_from_env
from .indexer import IndexingError, build_snapshot

app = typer.Typer(
    no_args_is_help=True,
    help="Select and run regression tests affected by a pull request.",
)


@app.command()
def index(
    repo: Path = typer.Option(Path("."), help="Path to the Python repository to index."),
    repo_id: str = typer.Option(..., help="Stable identifier for this repository in Atlas."),
    commit: str = typer.Option(..., help="Git commit SHA represented by the index."),
) -> None:
    """Index committed Python source, pytest tests, and dependency edges into Atlas."""
    try:
        snapshot = build_snapshot(repo, repo_id, commit)
        with graph_store_from_env() as store:
            store.save_snapshot(snapshot)
    except (GitError, IndexingError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None
    except PyMongoError:
        typer.echo("Atlas indexing failed. Check connectivity, credentials, and database permissions.", err=True)
        raise typer.Exit(code=2) from None
    except ValueError:
        typer.echo("Check MONGODB_URI and MONGODB_DATABASE in the environment or local .env file.", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(f"Indexed {len(snapshot.nodes)} nodes and {len(snapshot.edges)} edges "
               f"for {repo_id} at {snapshot.base_sha}.")


@app.command()
def analyze(
    repo: Path = typer.Option(Path("."), help="Path to the checked-out Python repository."),
    repo_id: str = typer.Option(..., help="Stable identifier for this repository in Atlas."),
    base: str = typer.Option(..., help="Base commit SHA for the pull request."),
    head: str = typer.Option(..., help="Head commit SHA for the pull request."),
    output: Path = typer.Option(Path("impact-report.json"), help="Path for the JSON report."),
    summary: Path = typer.Option(Path("impact-summary.md"), help="Path for the Markdown summary."),
) -> None:
    """Analyze a pull request and run selected tests (implementation pending)."""
    del repo, repo_id, base, head, output, summary
    typer.echo("The analyze command is scaffolded; see REQUIREMENTS.md tickets AGENT-1 and AGENT-2.", err=True)
    raise typer.Exit(code=2)
