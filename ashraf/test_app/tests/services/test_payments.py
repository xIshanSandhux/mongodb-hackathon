import pytest
from fastapi import HTTPException
from app.services.payments import main as payments
from app.services.payments.main import data, get_payment, create_payment


def test_payment_service_returns_seeded_payment():
    assert get_payment("pay_demo_1")["vendor"] == "Northstar Goods"


def test_payment_service_never_persists_pan_or_cvc():
    created = create_payment({"order_id":"ord_test_1", "customer_id":"cus_test", "customer_name":"Test User",
        "customer_email":"test@example.test", "vendor":"Northstar Goods", "vendor_id":"ven_northstar",
        "amount":12.5, "currency":"USD", "payment_method":"card", "capture_method":"automatic",
        "card_number":"4242424242424242", "card_cvc":"123", "card_exp_month":12,"card_exp_year":2030,"risk_decision":"approved"})
    stored = data[created["id"]]
    assert stored["card_last4"] == "4242"
    assert "card_number" not in stored and "card_cvc" not in stored


def test_payment_service_captures_manual_authorization(monkeypatch):
    monkeypatch.setitem(data, "pay_manual", {"id":"pay_manual", "status":"processing", "capture_method":"manual"})
    result = payments.capture("pay_manual")
    assert result["status"] == "succeeded"
    assert "captured_at" in result


def test_payment_service_allows_partial_then_full_refund(monkeypatch):
    payment = {"id":"pay_refund", "status":"succeeded", "capture_method":"automatic", "amount":20.0,
               "refunded_amount":0.0, "refunded_at":None}
    monkeypatch.setitem(data, "pay_refund", payment)
    partial = payments.refund("pay_refund", {"amount":5.0, "reason":"requested_by_customer"})
    assert partial["status"] == "partially_refunded"
    full = payments.refund("pay_refund", {"amount":15.0, "reason":"requested_by_customer"})
    assert full["status"] == "refunded"
    assert full["refunded_amount"] == 20.0


def test_payment_service_prevents_refund_over_remaining_balance(monkeypatch):
    monkeypatch.setitem(data, "pay_refund", {"id":"pay_refund", "status":"partially_refunded", "amount":20.0, "refunded_amount":18.0})
    with pytest.raises(HTTPException) as error:
        payments.refund("pay_refund", {"amount":3.0})
    assert error.value.status_code == 400
