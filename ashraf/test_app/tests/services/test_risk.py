from app.services.risk.main import decision_for


def test_risk_service_approves_ordinary_test_charge():
    result = decision_for("4242424242424242")
    assert result["decision"] == "approved"


def test_risk_service_declines_decline_scenario():
    result = decision_for("4242424242420002")
    assert result["decision"] == "declined"
