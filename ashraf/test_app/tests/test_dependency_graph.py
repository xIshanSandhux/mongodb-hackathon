from app.dependency_graph import downstream_services


def test_leaf_service_change_stays_inside_service():
    assert downstream_services("vendors") == set()
    assert downstream_services("payments") == set()


def test_reporting_change_includes_its_data_dependencies():
    assert downstream_services("reporting") == {"payments", "ledger", "notifications", "customers"}


def test_gateway_change_reaches_all_downstream_services():
    assert downstream_services("gateway") == {
        "customers", "vendors", "risk", "payments", "ledger", "notifications", "reporting"
    }


def test_dependency_chain_is_traversed_transitively():
    # Reporting calls ledger, which validates a payment with the payments service.
    assert downstream_services("reporting") >= {"ledger", "payments"}
