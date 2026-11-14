# TestEcho

An explainable CI agent that selects and runs regression tests for a pull request. Python indexing, graph impact tracing, test selection/execution, reports, and a default Atlas retrieval/memory adapter are implemented. Live Atlas integration and the separate demo/Actions workflow remain to be verified. See [PROBLEM.md](PROBLEM.md), [REQUIREMENTS.md](REQUIREMENTS.md), and [ARCH.md](ARCH.md) for scope and shared interfaces.

## Local dashboard

```sh
python -m pip install -e '.[dev,ui,payflow]'
python -m streamlit run streamlit_app.py
```

Open [TestEcho](http://127.0.0.1:8501). The short page flow is **Setup → Knowledge → Run → Results**: prepare a demo, index its base or continue with existing knowledge, then run TestEcho. Successful actions advance automatically. Results link to separate Explanation, Tests, Timing, and Reports pages; long evidence/logs stay in bounded panels. The interface uses MongoDB green/navy colors and displays **Powered by MongoDB**. Atlas credentials enable focused selection; without Atlas, actual full-suite tests still run and the reason is shown. `IMPACT_DEMO_REPO`, `IMPACT_DEMO_BASE`, and `IMPACT_DEMO_HEAD` can preconfigure a team repository; Local repository settings accept another checkout.

**PayFlow payments** uses [the real payments app](https://github.com/ash-raf-codes/payment_processing_app), cloned separately at a pinned commit. Choose its gateway validation refactor, deliberate local gateway regression, or historical vendor PR replay. TestEcho indexes the app's declared service dependencies as well as Python imports. The **Small starter** application remains available for quick synthetic examples. Reindex old snapshots after upgrading to graph schema version 2. See [PayFlow verification](docs/PAYFLOW-DEMO.md) for actual results and scope.

Set `GEMINI_API_KEY` in your ignored `.env` to enable automatic Gemini summaries. `GEMINI_MODEL` is configurable. Simple explanations are the default; switching to Developer reuses the same response. Without Gemini, an evidence-based template appears. Bounded evidence, relevant Python snippets, and failure logs may be sent to Gemini, with known secrets redacted. Do not use the demo with sensitive source you do not intend to share.

The full-suite baseline button executes real tests to measure a comparison; time savings remain **Not measured** until a matching baseline exists. Generated demos/reports live in temporary directories. The UI runs only on localhost and is not deployed.

## Runtime requirements

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

Run analysis with the demo repository checked out cleanly at head:

```sh
impact-agent analyze --repo /path/to/demo-repo --repo-id demo-python --base <base-sha> --head <head-sha> --output impact-report.json --summary impact-summary.md
```

The command merges graph, semantic, and prior-failure evidence, runs selected pytest tests or the full suite, saves run memory, and writes both reports. Failed tests return a failing exit status. Missing Atlas credentials/retrieval trigger full-suite fallback; unsuccessful memory storage is a visible warning. Reports must not overwrite tracked files. The demo's own dependencies must be installed into the Python environment running the agent.

The default vector index name is `knowledge_vector`; set `MONGODB_VECTOR_INDEX` if your team's index has another name. Person 1 still provisions and verifies the actual index. See [the graph handoff](docs/GRAPH-HANDOFF.md) and [the agent handoff](docs/AGENT-HANDOFF.md).

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

Add `--audit-missed-tests` to replay a passing focused run against the full suite and save any missed failures for later selection.
