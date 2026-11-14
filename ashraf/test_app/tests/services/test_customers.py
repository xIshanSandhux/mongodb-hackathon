import pytest
from pydantic import ValidationError
from app.services.customers.main import VerifyRequest, verify, records


def test_customer_service_verifies_and_reuses_customer(monkeypatch):
    records.clear()
    first = verify(VerifyRequest(name="Taylor Quinn", email="taylor@example.com", phone=None))
    second = verify(VerifyRequest(name="Taylor Quinn", email="taylor@example.com", phone=None))
    assert first["customer_id"] == second["customer_id"]


def test_customer_service_rejects_invalid_email():
    with pytest.raises(ValidationError):
        VerifyRequest(name="Taylor Quinn", email="not-an-email", phone=None)
