# PR Impact Agent

An explainable CI agent that selects and runs regression tests for a pull request. Python indexing and graph impact tracing are implemented; test selection/execution and CI integration remain separate tickets. See [PROBLEM.md](PROBLEM.md), [REQUIREMENTS.md](REQUIREMENTS.md), and [ARCH.md](ARCH.md) for scope and shared interfaces.

## Requirements

- Python 3.11 or newer
- Git
- MongoDB Atlas access for implementing and running the Atlas-backed features

Local graph checks were run with Python 3.14.3; the package supports Python 3.11 or newer.

## Set up on macOS / Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

## Set up on Windows PowerShell

From the repository root:

```powershell
py -3.12 -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

If Python 3.12 is not installed, use another supported Python version:

```powershell
py -m venv .venv
```

If PowerShell blocks activation, run the commands with the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Configure local environment

Edit `.env` and set `MONGODB_URI` to the connection string for your Atlas cluster. Keep real credentials in `.env` or your secret manager; `.env` is ignored by Git. Do not put Atlas credentials in source files or commit them.

The local environment file also supports:

```dotenv
MONGODB_URI=
MONGODB_DATABASE=pr_impact
REPO_ID=demo-python
```

## CLI

The package installs an `impact-agent` command. Check its available commands with:

```powershell
impact-agent --help
```

`index` creates the `knowledge` and `edges` collections and the `knowledge_vector` index if needed, then writes committed Python modules, symbols, pytest tests, edges, and a completion marker to Atlas:

```sh
impact-agent index --repo /path/to/demo-repo --repo-id demo-python --commit <base-sha>
```

`analyze` still exits with an implementation-pending message; Person 3 owns its integration. GRAPH-2 is available as `impact_agent.graph.analyze_graph`. See [the graph handoff](docs/GRAPH-HANDOFF.md) for usage and tests. Person 1 still owns vector index creation/search.

To run Person 1's live Atlas vector and prior-run smoke check separately, configure `MONGODB_URI` and run `python -m impact_agent.atlas`. The `index` command bootstraps the collections and vector index, but does not run this smoke check.

## Project layout

```text
src/impact_agent/   Python package and CLI
tests/              Automated tests (added with feature tickets)
PROBLEM.md          Product problem and success measures
REQUIREMENTS.md     MVP acceptance criteria and four-person tickets
ARCH.md             System architecture and interfaces
AGENTS.md           Instructions for Codex
```

The GitHub Actions workflow and sample Python application belong in a separate demo repository, as described in `ARCH.md`.

## How the pieces fit together

This project has three distinct parts:

- **Payments demo app** (`ashraf/test_app/`): a small FastAPI backend and browser dashboard that simulate payments, vendors, customers, captures, and refunds. It provides the application code and behavior used as the example system.
- **PR Impact Agent** (this repository): analyzes a pull request's code changes, selects relevant regression tests, runs them, and explains why each test was selected.
- **GitHub Actions** (the CI platform): starts workflows in response to repository events, runs scripts or actions on a runner, and reports the workflow result. In the planned setup, it triggers the PR Impact Agent and publishes the agent's report as a CI check.

GitHub Actions provides workflow automation; the PR Impact Agent provides the test-selection logic. The payments demo is the sample application the agent analyzes. The intended flow is: a pull request changes the payments app, GitHub Actions invokes the agent, and the agent selects and runs relevant tests and returns an explanation. See [GitHub's workflow overview](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows) for more about workflow triggers, jobs, and steps.
