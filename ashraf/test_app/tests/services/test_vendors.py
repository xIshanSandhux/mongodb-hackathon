from app.services.vendors.main import resolve, vendors


def test_vendor_service_lists_supported_vendors():
    assert len(vendors()["vendors"]) >= 3


def test_vendor_service_resolves_vendor_name():
    assert resolve("Northstar Goods")["id"] == "ven_northstar"
