import json
import pytest
from pathlib import Path
from src.models import ClaimInput, ReimbursementDecision
from src.agent import evaluate_claim


def load_claim(filename: str) -> ClaimInput:
    path = Path("data/claims") / filename
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("expected_decision", None)
    return ClaimInput(**data)


@pytest.fixture(scope="module")
def decision_001():
    return evaluate_claim(load_claim("claim_001_approved.json"))


@pytest.fixture(scope="module")
def decision_002():
    return evaluate_claim(load_claim("claim_002_partial.json"))


@pytest.fixture(scope="module")
def decision_003():
    return evaluate_claim(load_claim("claim_003_rejected.json"))


@pytest.fixture(scope="module")
def decision_004():
    return evaluate_claim(load_claim("claim_004_manual_review.json"))


class TestClaim001Approved:
    def test_decision_is_approve(self, decision_001):
        assert decision_001.decision == "Approve"

    def test_approved_amount_positive(self, decision_001):
        assert decision_001.approved_amount > 0

    def test_rejected_amount_minimal(self, decision_001):
        assert decision_001.rejected_amount < 50

    def test_confidence_high(self, decision_001):
        assert decision_001.confidence >= 0.8

    def test_audit_trail_not_empty(self, decision_001):
        assert len(decision_001.audit_trail) >= 2


class TestClaim002Partial:
    def test_decision_is_partial(self, decision_002):
        assert decision_002.decision in ("Partially Approve", "Manual Review")

    def test_has_deductions(self, decision_002):
        assert len(decision_002.deductions) > 0

    def test_approved_less_than_claimed(self, decision_002):
        assert decision_002.approved_amount < 1640.0

    def test_rejected_amount_positive(self, decision_002):
        assert decision_002.rejected_amount > 0


class TestClaim003Rejected:
    def test_decision_is_reject(self, decision_003):
        assert decision_003.decision in ("Reject", "Manual Review")

    def test_approved_amount_minimal_or_zero(self, decision_003):
        assert decision_003.approved_amount < 500


class TestClaim004ManualReview:
    def test_decision_is_manual_review(self, decision_004):
        assert decision_004.decision == "Manual Review"

    def test_routed_to_manual_queue(self, decision_004):
        assert "Manual" in decision_004.routed_to


class TestTools:
    def test_policy_lookup_returns_content(self):
        from src.tools import policy_lookup
        result = policy_lookup.invoke({"query": "hotel"})
        assert "hotel" in result.lower() or "accommodation" in result.lower()

    def test_limit_checker_within(self):
        from src.tools import limit_checker
        result = limit_checker.invoke({"category": "flight", "amount": 500.0, "unit": "domestic"})
        assert "Within limit: True" in result

    def test_limit_checker_exceeded(self):
        from src.tools import limit_checker
        result = limit_checker.invoke({"category": "hotel", "amount": 250.0, "unit": "per_night"})
        assert "Within limit: False" in result

    def test_receipt_validator_missing(self):
        from src.tools import receipt_validator
        items = [{"description": "Flight", "amount": 300.0, "has_receipt": False, "category": "flight"}]
        result = receipt_validator.invoke({"expenses": items})
        assert "Missing receipts" in result

    def test_receipt_validator_all_present(self):
        from src.tools import receipt_validator
        items = [{"description": "Taxi", "amount": 30.0, "has_receipt": True, "category": "ground_transport"}]
        result = receipt_validator.invoke({"expenses": items})
        assert "All required receipts are present" in result

    def test_duplicate_detector_no_dup(self):
        from src.tools import duplicate_detector
        result = duplicate_detector.invoke({"employee_id": "EMP-9999", "start_date": "2025-01-01", "category": "flight"})
        assert "No duplicate" in result

    def test_approval_threshold_auto(self):
        from src.tools import approval_threshold
        result = approval_threshold.invoke({"total_amount": 150.0})
        assert "Automated" in result

    def test_approval_threshold_manager(self):
        from src.tools import approval_threshold
        result = approval_threshold.invoke({"total_amount": 800.0})
        assert "Manager" in result or "Direct" in result
