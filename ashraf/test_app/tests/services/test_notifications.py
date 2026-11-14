import asyncio
from types import SimpleNamespace

from app.services.notifications import main as notifications


class CustomerLookup:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def get(self, path, params): return SimpleNamespace(raise_for_status=lambda: None)


def test_notification_records_verified_payment_event(monkeypatch):
    monkeypatch.setattr(notifications.httpx, "AsyncClient", lambda **kwargs: CustomerLookup())
    monkeypatch.setattr(notifications, "events", [])
    event = asyncio.run(notifications.notify(notifications.Notice(
        payment_id="pay_test", customer_email="customer@example.com", event="payment.succeeded")))
    assert event["delivery"] == "simulated"
    assert notifications.list_events()["count"] == 1
