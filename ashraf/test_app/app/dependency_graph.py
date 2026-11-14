"""Impact graph oriented from changed dependency to its dependent consumers.

Following outgoing edges finds services and integration tests that may be
affected by a change in the source service.
"""

SERVICE_DEPENDENTS = {
    "gateway": set(),
    "customers": {"gateway", "notifications"},
    "vendors": {"gateway", "risk", "fraud", "webhooks"},
    "fx": {"gateway"},
    "fraud": {"gateway"},
    "risk": {"gateway"},
    "idempotency": {"gateway"},
    "payments": {"gateway", "ledger", "settlement", "disputes", "reporting"},
    "ledger": {"gateway", "settlement", "disputes", "reporting"},
    "settlement": {"gateway", "reporting"},
    "disputes": {"gateway", "reporting"},
    "notifications": {"gateway", "reporting"},
    "webhooks": {"gateway"},
    "audit": {"gateway"},
    "reporting": {"gateway"},
}

# Retain the prior exported name for callers, but document its impact direction.
SERVICE_CALLS = SERVICE_DEPENDENTS


def downstream_services(service: str) -> set[str]:
    """Return all transitive consumers affected by changing `service`."""
    if service not in SERVICE_DEPENDENTS:
        raise KeyError(f"Unknown service: {service}")
    discovered: set[str] = set()
    pending = list(SERVICE_DEPENDENTS[service])
    while pending:
        current = pending.pop()
        if current in discovered:
            continue
        discovered.add(current)
        pending.extend(SERVICE_DEPENDENTS[current] - discovered)
    return discovered
