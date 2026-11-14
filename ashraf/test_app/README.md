# PayFlow demo payments app

A payments operations demo with 15 independently runnable FastAPI services and a browser frontend. It includes payment authorization, fraud review, FX quotes, duplicate-request protection, ledgering, settlement, disputes, notifications, webhooks, audit records, and reporting. It is designed as the PR Impact Agent's sample application. Service boundaries and calls are documented in [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md).

## Run the services together

From this directory, start the gateway and all domain services with Docker Compose:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. Gateway API docs are at http://127.0.0.1:8000/docs. Each service also has its own `/docs` endpoint on internal ports 8101–8114.

Stop all services with `Ctrl+C` or `docker compose down`.

To run a single service during development, install `requirements.txt` and run, for example:

```bash
uvicorn app.main:app --reload --port 8000
uvicorn app.services.payments.main:app --reload --port 8101
```

Set the service URL environment variables (`PAYMENTS_URL`, `CUSTOMERS_URL`, `VENDORS_URL`, `RISK_URL`, `LEDGER_URL`, `NOTIFICATIONS_URL`, `REPORTING_URL`, `FX_URL`, `FRAUD_URL`, `IDEMPOTENCY_URL`, `SETTLEMENT_URL`, `DISPUTES_URL`, `WEBHOOKS_URL`, `AUDIT_URL`) to override service addresses. Compose wires these automatically.

## Demo behavior

- View and filter payment transactions.
- Submit a mock payment with vendor, customer, and card test details; no real payment network is contacted.
- Inspect payment details, capture manually authorized payments, and issue full or partial refunds.
- Screen payments for fraud, quote settlement currency, enforce idempotency, queue payouts, open disputes, and record audit and webhook events.
- The backend validates customer email/phone, order IDs, amounts, card checksum, expiration, CVC shape, vendor, and payment state transitions.
- Card brand, expiration, and last four digits are retained. Full card number and CVC are never stored.
- API endpoints include `/api/dashboard/summary`, `/api/vendors`, `/api/customers`, `/api/payments` (search, filter, pagination), payment detail, capture, and refund.
- Each service owns its API and in-memory demo state; records reset when that service restarts.
- The gateway health endpoint reports service availability at `/api/health`.

All payment details are fictional. Do not enter real card data. This service split demonstrates service boundaries and synchronous HTTP dependencies; it is a hackathon demo, not a production payment platform.

## Test suites for impact analysis

Install the test dependencies with `pip install -r requirements-dev.txt`, then run `pytest -q`. Tests are grouped by service; gateway tests cover the multi-service payment path and graph tests check impact traversal. The current suite has 54 cases. A vendor change fans out to Vendor, Fraud, Risk, Webhooks, and Gateway coverage; a gateway change has no downstream consumers and stays within Gateway and graph tests.

To compare blind full-suite CI with graph-focused selection, run `python scripts/compare_test_runs.py --changed-service vendors`. The script reports test counts and measured runtime for both runs. Try `payments`, `vendors`, or `gateway` to see how different dependency neighborhoods change the selection. This local benchmark demonstrates the graph idea; the PR Impact Agent CLI will provide the integrated selection in CI.
