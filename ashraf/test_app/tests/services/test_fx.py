import pytest
from fastapi import HTTPException
from app.services.fx.main import quote
from pytest import mark


def test_fx_service_converts_supported_currencies_to_settlement_currency():
    result = quote(amount=100, currency="EUR")
    assert result["settlement_currency"] == "USD"
    assert result["settlement_amount"] == 108


def test_fx_service_rejects_unsupported_currency():
    with pytest.raises(HTTPException) as error:
        quote(amount=100, currency="GBP")
    assert error.value.status_code == 422


@mark.parametrize(("currency", "expected"), [("USD", 10), ("CAD", 7.4), ("EUR", 10.8)])
def test_fx_service_applies_currency_rates(currency, expected):
    assert quote(amount=10, currency=currency)["settlement_amount"] == expected
