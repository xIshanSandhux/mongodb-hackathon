from app.services.webhooks.main import Webhook


def test_webhook_service_validates_delivery_event_shape():
    event=Webhook(event="payment.succeeded", resource_id="pay_123", vendor_id="ven_acme")
    assert event.resource_id == "pay_123"
