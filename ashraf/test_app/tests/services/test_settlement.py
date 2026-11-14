import pytest
from pydantic import ValidationError
from app.services.settlement.main import Settlement, settlements


def test_settlement_service_requires_positive_amount():
    with pytest.raises(ValidationError):
        Settlement(payment_id="pay_1", amount=0, currency="USD", vendor_id="ven_acme")


def test_settlement_service_tracks_pending_vendor_payout(monkeypatch):
    monkeypatch.setattr("app.services.settlement.main.settlements", [])
    # The HTTP dependency checks are covered by the integration contract; this validates the service document shape.
    from app.services.settlement import main as settlement
    item={"id":"set_test", **Settlement(payment_id="pay_1", amount=14.5, currency="USD", vendor_id="ven_acme").model_dump()}
    settlement.settlements.append(item)
    assert settlement.list_settlements()["settlements"][0]["status"] == "pending"
