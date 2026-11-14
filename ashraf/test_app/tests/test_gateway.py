import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.main import PaymentRequest, app, create_payment


def test_gateway_validates_payment_request_and_card_data():
    with pytest.raises(ValidationError):
        PaymentRequest(order_id="x", customer_name="A", customer_email="bad", amount="10.001", vendor="Unknown", card_number="123")


def test_gateway_rejects_expired_card():
    with pytest.raises(ValidationError):
        PaymentRequest(order_id="ord_1", customer_name="Sam User", customer_email="sam@example.com", amount="10.00",
                       vendor="Acme Store", card_number="4242424242424242", card_exp_month=1,
                       card_exp_year=2020, card_cvc="123")


def test_gateway_payment_flow_calls_all_required_services(monkeypatch):
    calls = []
    responses = {
        ("idempotency", "/idempotency/reserve"): {"payment_id":None,"replayed":False},
        ("customers", "/customers/verify"): {"customer_id":"cus_1"},
        ("vendors", "/vendors/resolve"): {"id":"ven_northstar"},
        ("fx", "/fx/quote"): {"settlement_amount":12.5,"settlement_currency":"USD"},
        ("fraud", "/fraud/screen"): {"decision":"allow","score":0},
        ("risk", "/risk/authorize"): {"decision":"approved"},
        ("payments", "/payments"): {"id":"pay_1", "amount":12.5, "currency":"USD", "status":"succeeded", "customer_email":"x@example.com"},
        ("ledger", "/ledger/entries"): {"id":"led_1"},
        ("notifications", "/notifications"): {"id":"evt_1"},
        ("settlement", "/settlements"): {"id":"set_1"},
        ("webhooks", "/webhooks/deliver"): {"id":"whd_1"},
        ("audit", "/audit/events"): {"id":"aud_1"},
        ("idempotency", "/idempotency/idem_"): {"payment_id":"pay_1"},
    }

    async def fake_call(service, method, path, **kwargs):
        calls.append((service, path))
        if service == "idempotency" and path.startswith("/idempotency/") and path.endswith("/complete"):
            return responses[("idempotency", "/idempotency/idem_")]
        return responses[(service, path)]

    monkeypatch.setattr("app.main.call", fake_call)
    request = PaymentRequest(order_id="ord_123", customer_name="Sam User", customer_email="sam@example.com",
                             amount="12.50", vendor="Northstar Goods")
    result = asyncio.run(create_payment(request))
    assert result["id"] == "pay_1"
    assert [service for service, _ in calls] == ["idempotency", "customers", "vendors", "fx", "fraud", "risk",
        "payments", "ledger", "notifications", "settlement", "webhooks", "audit", "idempotency"]
