# PayFlow demo payments app

A small payments processing demo made of independently runnable FastAPI services and a browser frontend. It is designed as the PR Impact Agent's sample application. Service boundaries and calls are documented in [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md).

## Run the services together

From this directory, start the gateway and all domain services with Docker Compose:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. Gateway API docs are at http://127.0.0.1:8000/docs. Each service also has its own `/docs` endpoint on its internal port (8101–8107).

Stop all services with `Ctrl+C` or `docker compose down`.

To run a single service during development, install `requirements.txt` and run, for example:

```bash
uvicorn app.main:app --reload --port 8000
uvicorn app.services.payments.main:app --reload --port 8101
```

Set `PAYMENTS_URL`, `CUSTOMERS_URL`, `VENDORS_URL`, `RISK_URL`, `LEDGER_URL`, `NOTIFICATIONS_URL`, and `REPORTING_URL` to override service addresses. The Compose file provides these service locations automatically.

## Demo behavior

- View and filter payment transactions.
- Submit a mock payment with vendor, customer, and card test details; no real payment network is contacted.
- Inspect payment details, capture manually authorized payments, and issue full or partial refunds.
- The backend validates customer email/phone, order IDs, amounts, card checksum, expiration, CVC shape, vendor, and payment state transitions.
- Card brand, expiration, and last four digits are retained. Full card number and CVC are never stored.
- API endpoints include `/api/dashboard/summary`, `/api/vendors`, `/api/customers`, `/api/payments` (search, filter, pagination), payment detail, capture, and refund.
- Each service owns its API and in-memory demo state; records reset when that service restarts.
- The gateway health endpoint reports service availability at `/api/health`.

All payment details are fictional. Do not enter real card data. This service split demonstrates service boundaries and synchronous HTTP dependencies; it is a hackathon demo, not a production payment platform.
