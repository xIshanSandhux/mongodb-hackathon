# PayFlow payments demo

Source: [ash-raf-codes/payment_processing_app](https://github.com/ash-raf-codes/payment_processing_app). TestEcho uses a separate clone and never pushes or edits the upstream checkout.

## Prepare and run

```sh
python -m pip install -e '.[dev,ui,payflow]'
python -m streamlit run streamlit_app.py
```

On Setup, leave **PayFlow payments** selected, choose a scenario, and click **Prepare & continue**. On Knowledge, **Index base in Atlas** (required after the graph-schema upgrade), then **Run TestEcho**. The workflow remains on separate short pages. PayFlow source is downloaded on explicit preparation; tests require the optional `payflow` dependencies above. No package installation occurs through the UI.

The provider/consumer map in `app/dependency_graph.py` is read as literal AST data, without executing application code during indexing. Its 28 declared HTTP dependency edges appear as `service_call` relationships with a metadata-file evidence path. Registry mutations/dynamic definitions are unsupported and rejected; changing the registry file requires full-suite fallback. Snapshot schema version 2 prevents an old import-only index from silently being treated as complete.

## Scenarios and provenance

| Scenario | Base | Head | Source change |
| --- | --- | --- | --- |
| Gateway validation refactor | `7d80d2eea28b6ee604cdb14781ff5f72303079a6` | New local replay commit | Equivalent Decimal precision comparison in `app/main.py` |
| Gateway regression | Same pinned snapshot | New local replay commit | Deliberately disables the precision rejection in the separate demo clone |
| Vendor PR replay | `e9b8d83a2b9fc33a95eb152c9e4880d1e7646332` | `827cc148542f405f517a07e615de74b5a3ce5e47` | Original upstream processor-region metadata change and its test |

The first two are explicitly generated local scenarios, not historical upstream regressions. The third uses original commits without generated edits. All report SHAs are actual Git commits. A fresh separate clone is created for each preparation, and the stable Atlas repo ID is `payflow-demo` so prior outcomes remain retrievable across replays.

## Verified results — November 14, 2026

The unmodified pinned app passed its full suite: **55 tests**, using Python 3.14.3 and the repository's documented test dependencies. A source snapshot produced 189 nodes, 146 `tested_by`, 66 `imports`, and 28 `service_call` edges.

| Replay | Selected / full cases | Test result | Full-suite comparison | Atlas memory |
| --- | --- | --- | --- | --- |
| Gateway validation refactor | 39 / 55 | Passed | Passed | Saved |
| Gateway regression | 36 / 55 | Failed | Failed | Saved |
| Vendor PR replay | 27 / 55 | Passed | Passed | Saved |

The failing case was `tests/test_gateway_validation_matrix.py::test_gateway_rejects_invalid_payment_fields[amount-24.951]`. A real Gemini response generated Simple/Developer explanations for that failing report.

These are observed selections, not fixed expectations: as embeddings become available and prior-run memory changes, future candidate counts may differ. The focused run took about 27.57s versus a 0.41s full-suite baseline; the regression run about 11.80s versus 0.41s; the historical replay about 5.68s versus 0.53s. No end-to-end speedup is established for this very small test workload.

Tests exercise the real PayFlow Python code and mock service HTTP calls. Docker services, distributed HTTP behavior, real payment networks, and the payments frontend were not deployed or tested by this replay. All payment data is fictional.

## CI status

The source repository now contains `.github/workflows/pr-impact.yml`, including base indexing, report publication, and a pinned agent dependency. Its inspected Actions run [43642727008](https://github.com/ash-raf-codes/payment_processing_app/actions/runs/43642727008) failed at **Check Atlas connection**. Local TestEcho verification does not establish a passing Actions run.

The team must fix that workflow's Atlas access/secret and update `AGENT_REF` to a published, reviewed agent commit containing service-map support. This integration does not change credentials, workflows, or branches in the source repository.
