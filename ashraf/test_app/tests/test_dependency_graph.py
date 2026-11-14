from app.dependency_graph import downstream_services


def test_leaf_service_change_stays_inside_service():
    assert downstream_services("gateway") == set()


def test_reporting_change_includes_its_data_dependencies():
    assert downstream_services("reporting") == {"gateway"}


def test_vendor_change_reaches_transitive_consumers():
    assert downstream_services("vendors") == {"gateway", "risk", "fraud", "webhooks"}


def test_payment_change_reaches_financial_consumers_and_gateway():
    assert downstream_services("payments") == {"gateway", "ledger", "settlement", "disputes", "reporting"}
