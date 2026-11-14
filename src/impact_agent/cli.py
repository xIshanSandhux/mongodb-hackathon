"""Command-line entry point for the PR Impact Agent MVP."""

from pathlib import Path

import typer

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
    """Index a Python repository into MongoDB Atlas (implementation pending)."""
    typer.echo("The index command is scaffolded; see REQUIREMENTS.md ticket GRAPH-1.", err=True)
    raise typer.Exit(code=2)


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
