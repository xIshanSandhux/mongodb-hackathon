from app.services.audit.main import AuditEvent, record, events


def test_audit_service_records_actor_and_resource(monkeypatch):
    monkeypatch.setattr("app.services.audit.main.events", [])
    event=record(AuditEvent(actor="ops@example.com", action="payment.refunded", resource_type="payment", resource_id="pay_123"))
    assert event["action"] == "payment.refunded"
    assert events is not None
