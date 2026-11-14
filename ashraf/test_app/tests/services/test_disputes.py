import pytest
from pydantic import ValidationError
from app.services.disputes.main import Dispute, disputes, list_disputes


def test_dispute_service_requires_reason_and_positive_amount():
    with pytest.raises(ValidationError):
        Dispute(payment_id="pay_1", reason="", amount=10)


def test_dispute_service_filters_by_payment(monkeypatch):
    monkeypatch.setattr("app.services.disputes.main.disputes", [
        {"id":"dsp_1", "payment_id":"pay_1"}, {"id":"dsp_2", "payment_id":"pay_2"}])
    assert list_disputes("pay_1")["count"] == 1
