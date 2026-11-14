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
