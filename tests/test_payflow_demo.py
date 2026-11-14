from impact_agent.payflow_demo import prepare_payflow_demo, PAYFLOW_SCENARIOS
from impact_agent.gitrepo import git, resolve_commit
from impact_agent.runner import run_tests


def baseline(git_repo):
    repo, commit = git_repo
    sha = commit({
        "app/__init__.py": "",
        "app/main.py": "from decimal import Decimal\ndef validate(value):\n    if value != value.quantize(Decimal(\"0.01\")):\n        raise ValueError('precision')\n    return value\n",
        "tests/test_gateway.py": "from decimal import Decimal\nimport pytest\nfrom app.main import validate\ndef test_bad_precision():\n    with pytest.raises(ValueError):\n        validate(Decimal('10.001'))\n",
        "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['.']\ntestpaths = ['tests']\n",
        ".gitignore": "__pycache__/\n.pytest_cache/\n",
    })
    return repo, sha


def test_payflow_refactor_keeps_source_separate_and_passes(git_repo, tmp_path_factory):
    source, sha = baseline(git_repo)
    demo = prepare_payflow_demo(PAYFLOW_SCENARIOS[0], source=source, revision=sha,
                               parent=tmp_path_factory.mktemp("payflow-clones"))
    assert demo.repo != source and demo.base == sha and demo.head != sha
    assert resolve_commit(source, "HEAD") == sha
    assert git(source, "status", "--porcelain") == b""
    assert demo.source_url == "https://github.com/ash-raf-codes/payment_processing_app"
    assert demo.generated_change
    assert run_tests(demo.repo).exit_code == 0


def test_payflow_regression_produces_actual_failing_test(git_repo, tmp_path_factory):
    source, sha = baseline(git_repo)
    demo = prepare_payflow_demo(PAYFLOW_SCENARIOS[1], source=source, revision=sha,
                               parent=tmp_path_factory.mktemp("payflow-regressions"))
    result = run_tests(demo.repo)
    assert result.exit_code == 1
    assert result.outcomes[0]["outcome"] == "failed"
