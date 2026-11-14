import pytest
from fastapi import HTTPException
from app.services.vendors.main import resolve, vendors


def test_vendor_service_lists_supported_vendors():
    assert len(vendors()["vendors"]) >= 3


def test_vendor_service_resolves_vendor_name():
    assert resolve("Northstar Goods")["id"] == "ven_northstar"


def test_vendor_service_rejects_unknown_vendor():
    with pytest.raises(HTTPException) as error:
        resolve("Imaginary Shop")
    assert error.value.status_code == 404
