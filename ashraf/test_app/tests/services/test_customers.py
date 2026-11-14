from app.services.customers.main import VerifyRequest, verify, records


def test_customer_service_verifies_and_reuses_customer(monkeypatch):
    records.clear()
    first = verify(VerifyRequest(name="Taylor Quinn", email="taylor@example.test", phone=None))
    second = verify(VerifyRequest(name="Taylor Quinn", email="taylor@example.test", phone=None))
    assert first["customer_id"] == second["customer_id"]
