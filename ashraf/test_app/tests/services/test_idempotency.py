import pytest
from fastapi import HTTPException
from app.services.idempotency import main as idempotency


def test_idempotency_service_replays_matching_request(monkeypatch):
    monkeypatch.setattr(idempotency, "keys", {})
    payload={"key":"idem_request_1", "request_fingerprint":"fingerprint-1"}
    first=idempotency.reserve(idempotency.Reservation(**payload))
    second=idempotency.reserve(idempotency.Reservation(**payload))
    assert first["replayed"] is False and second["replayed"] is True


def test_idempotency_service_rejects_key_reuse_for_different_request(monkeypatch):
    monkeypatch.setattr(idempotency, "keys", {})
    idempotency.reserve(idempotency.Reservation(key="idem_request_2", request_fingerprint="fingerprint-1"))
    with pytest.raises(HTTPException) as error:
        idempotency.reserve(idempotency.Reservation(key="idem_request_2", request_fingerprint="fingerprint-2"))
    assert error.value.status_code == 409


def test_idempotency_service_completes_key_with_payment_reference(monkeypatch):
    monkeypatch.setattr(idempotency, "keys", {})
    idempotency.reserve(idempotency.Reservation(key="idem_complete_1", request_fingerprint="fingerprint-1"))
    result=idempotency.complete("idem_complete_1", {"payment_id":"pay_abc"})
    assert result["payment_id"] == "pay_abc"
