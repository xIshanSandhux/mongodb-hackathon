"""Runtime service-call graph used for impact-analysis examples and health tooling.

Edges point from a caller to the service it invokes. The impact agent should run
tests for the changed service, then follow these outgoing edges for downstream
integration coverage.
"""

SERVICE_CALLS = {
    "gateway": {"customers", "vendors", "risk", "payments", "ledger", "notifications", "reporting"},
    "customers": set(),
    "vendors": set(),
    "risk": {"vendors"},
    "payments": set(),
    "ledger": {"payments"},
    "notifications": {"customers"},
    "reporting": {"payments", "ledger", "notifications"},
}


def downstream_services(service: str) -> set[str]:
    """Return the transitive set of services called by `service`."""
    if service not in SERVICE_CALLS:
        raise KeyError(f"Unknown service: {service}")
    discovered: set[str] = set()
    pending = list(SERVICE_CALLS[service])
    while pending:
        current = pending.pop()
        if current in discovered:
            continue
        discovered.add(current)
        pending.extend(SERVICE_CALLS[current] - discovered)
    return discovered
