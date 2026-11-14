"""Command-line entry point for the PR Impact Agent MVP."""

from contextlib import ExitStack
import os
from pathlib import Path

import typer
from pymongo.errors import PyMongoError

from .atlas import VECTOR_INDEX, atlas_database, create_atlas_client, setup_atlas
from .gitrepo import GitError
from .graph_store import AtlasGraphStore, graph_store_from_env
from .indexer import IndexingError, build_snapshot
from .agent import analyze_repository
from .retrieval import AtlasRetrievalStore

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
    """Set up Atlas and index committed Python source, tests, and graph edges."""
    try:
        snapshot = build_snapshot(repo, repo_id, commit)
        with create_atlas_client() as client:
            database = atlas_database(client)
            setup_atlas(database)
            AtlasGraphStore(database).save_snapshot(snapshot)
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
    audit_missed_tests: bool = typer.Option(False, "--audit-missed-tests", help="Audit passing focused runs with full pytest."),
) -> None:
    """Select regression tests, run pytest, remember outcomes, and write reports."""
    try:
        with ExitStack() as stack:
            try:
                graph_store = stack.enter_context(graph_store_from_env())
            except (PyMongoError, ValueError):
                graph_store = None
            retrieval = (AtlasRetrievalStore(
                graph_store.knowledge,
                os.environ.get("MONGODB_VECTOR_INDEX", VECTOR_INDEX),
            ) if graph_store is not None else None)
            report = analyze_repository(repo, repo_id, base, head, output, summary, graph_store, retrieval)
    except (ValueError, OSError):
        typer.echo("Analysis could not write its reports. Check distinct report paths, permissions, and repository files.", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(f"Tests: {report['test_status']}; cases: {report['selected_test_count']}; "
               f"full-suite fallback: {'yes' if report['fallback']['ran'] else 'no'}.")
    typer.echo(f"Reports: {output} and {summary}")
    if report["persistence"]["status"] in ("failed", "unavailable"):
        typer.echo(report["persistence"]["warning"], err=True)
    raise typer.Exit(code=report["exit_code"])
