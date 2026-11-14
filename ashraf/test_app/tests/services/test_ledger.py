import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.ledger import main as ledger


class PaymentLookup:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def get(self, path): return SimpleNamespace(raise_for_status=lambda: None)


def test_ledger_records_entry_after_verifying_payment(monkeypatch):
    monkeypatch.setattr(ledger.httpx, "AsyncClient", lambda **kwargs: PaymentLookup())
    monkeypatch.setattr(ledger, "entries", [])
    entry = asyncio.run(ledger.create_entry(ledger.Entry(payment_id="pay_test", amount=10, currency="USD", type="charge", status="succeeded")))
    assert entry["payment_id"] == "pay_test"
    assert ledger.list_entries("pay_test")["count"] == 1


def test_ledger_rejects_when_payment_service_is_unavailable(monkeypatch):
    class BrokenLookup(PaymentLookup):
        async def get(self, path): raise ledger.httpx.ConnectError("offline")
    monkeypatch.setattr(ledger.httpx, "AsyncClient", lambda **kwargs: BrokenLookup())
    with pytest.raises(HTTPException) as error:
        asyncio.run(ledger.create_entry(ledger.Entry(payment_id="pay_unknown", amount=10, currency="USD", type="charge", status="succeeded")))
    assert error.value.status_code == 503
