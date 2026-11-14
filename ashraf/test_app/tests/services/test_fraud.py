from app.services.fraud.main import ScreeningRequest, assess
import pytest


def test_fraud_service_allows_normal_transaction():
    result = assess(ScreeningRequest(amount=25, currency="USD", customer_email="buyer@example.com", vendor_id="ven_acme"))
    assert result["decision"] == "allow"


def test_fraud_service_flags_high_value_transaction_for_review():
    result = assess(ScreeningRequest(amount=2500, currency="USD", customer_email="buyer@example.com", vendor_id="ven_acme"))
    assert result["decision"] == "review"
    assert "high_amount" in result["flags"]


@pytest.mark.parametrize("amount", [1000, 2500, 10000])
def test_fraud_service_flags_high_value_threshold(amount):
    result = assess(ScreeningRequest(amount=amount, currency="USD", customer_email="buyer@example.com", vendor_id="ven_acme"))
    assert result["decision"] == "review"
    assert result["score"] == 45
