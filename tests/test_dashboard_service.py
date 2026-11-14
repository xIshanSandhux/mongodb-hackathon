from impact_agent.dashboard_service import prepare_demo, analyze_local, dashboard_metrics, benchmark_full_suite


def test_prepared_demo_is_a_separate_real_repo_with_replayable_commits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    demo = prepare_demo("Regression", parent=tmp_path)
    assert (demo.repo / ".git").is_dir() and demo.base != demo.head
    report, _, _ = analyze_local(demo.repo, demo.repo_id, demo.base, demo.head)
    assert report["exit_code"] == 1 and report["test_status"] == "failed"
    assert report["selected_test_count"] > 0


def test_metrics_never_invent_a_time_baseline():
    report = {"head_sha": "head", "repo_id": "demo", "full_suite_count": 10,
              "test_status": "passed",
              "selected_test_count": 2, "duration_seconds": 3, "test_duration_seconds": 1,
              "test_outcomes": [{"outcome": "passed"}, {"outcome": "failed"}]}
    metrics = dashboard_metrics(report)
    assert metrics["test_reduction"] == 80 and metrics["time_saved"] is None
    baseline = {"head_sha": "wrong", "repo_id": "demo", "duration_seconds": 6, "exit_code": 0}
    assert dashboard_metrics(report, baseline)["time_saved"] is None
    baseline["head_sha"] = "head"
    assert dashboard_metrics(report, baseline)["time_saved"] == 3
    report["test_status"] = "not_run"
    assert dashboard_metrics(report, baseline)["time_saved"] is None


def test_full_suite_benchmark_executes_actual_tests(tmp_path):
    demo = prepare_demo("Focused change", parent=tmp_path)
    result = benchmark_full_suite(demo.repo, demo.repo_id, demo.head)
    assert result["exit_code"] == 0 and result["case_count"] > 1


def test_failure_count_includes_omitted_tests_found_by_audit():
    report = {"test_status": "failed", "test_outcomes": [{"test_id": "selected", "outcome": "passed"}],
              "missed_test_audit": {"missed_failures": [{"test_id": "missed", "outcome": "failed"}]}}
    assert dashboard_metrics(report)["failed"] == 1
