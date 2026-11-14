import pytest
from pydantic import ValidationError

from app.main import PaymentRequest

BASE = {
    "order_id":"ord_matrix_1", "customer_name":"Jordan Lee", "customer_email":"jordan@example.com",
    "amount":"24.95", "vendor":"Northstar Goods",
}


@pytest.mark.parametrize(("field", "value"), [
    ("order_id", "bad order id"),
    ("order_id", "x"),
    ("customer_name", "J"),
    ("customer_email", "not-an-email"),
    ("amount", "0"),
    ("amount", "24.951"),
    ("amount", "100001"),
    ("currency", "GBP"),
    ("card_number", "4242424242424241"),
    ("card_number", "123"),
    ("card_cvc", "12"),
])
def test_gateway_rejects_invalid_payment_fields(field, value):
    payload = {**BASE, field:value}
    if field in {"card_number", "card_cvc"}:
        payload.update(card_number="4242424242424242", card_exp_month=12, card_exp_year=2030, card_cvc="123")
        payload[field] = value
    with pytest.raises(ValidationError):
        PaymentRequest(**payload)


def test_gateway_accepts_valid_card_and_normalizes_pan():
    request = PaymentRequest(**BASE, card_number="4242 4242 4242 4242", card_exp_month=12,
                             card_exp_year=2030, card_cvc="123")
    assert request.card_number == "4242424242424242"
