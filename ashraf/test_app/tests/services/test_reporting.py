import asyncio
from types import SimpleNamespace

from app.services.reporting import main as reporting


class Response:
    def __init__(self, body): self.body = body
    def raise_for_status(self): pass
    def json(self): return self.body


class ReportingClient:
    def __init__(self, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def get(self, url, **kwargs):
        if url.endswith("/payments"): return Response({"payments":[
            {"status":"succeeded", "amount":15.25,"vendor":"Northstar Goods","refunded_amount":0},
            {"status":"refunded", "amount":4,"vendor":"Morrow Home","refunded_amount":4}]})
        if url.endswith("/ledger/entries"): return Response({"count":3})
        if url.endswith("/notifications"): return Response({"count":2})
        if url.endswith("/settlements"): return Response({"count":4})
        return Response({"count":1})


def test_reporting_aggregates_payment_and_downstream_service_data(monkeypatch):
    monkeypatch.setattr(reporting.httpx, "AsyncClient", ReportingClient)
    summary = asyncio.run(reporting.summary())
    assert summary["successful_volume"] == 15.25
    assert summary["refunded_volume"] == 4
    assert summary["ledger_entries"] == 3
    assert summary["notification_events"] == 2
    assert summary["settlements"] == 4
    assert summary["disputes"] == 1
