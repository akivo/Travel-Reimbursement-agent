from langchain.tools import tool
from src.policy_store import search_policy, get_limit, get_approval_tier

_submitted_claims: dict = {
    "EMP-9999-2025-05-01": "CLM-000"
}


@tool
def policy_lookup(query: str) -> str:
    """Search the travel policy for rules relevant to a given topic or expense category."""
    return search_policy(query)


@tool
def limit_checker(category: str, amount: float, unit: str = "total") -> str:
    """
    Check if an expense amount is within policy limits.
    category: flight | hotel | meals | ground_transport
    unit: domestic | international | per_night | per_day | per_trip | per_mile
    For hotel, pass the per-night rate. For meals, pass the per-day amount.
    """
    limits = get_limit(category)
    limit_map = {
        "per_night":     "per_night_max",
        "per_day":       "per_diem_per_day",
        "per_trip":      "taxi_per_trip_max",
        "domestic":      "domestic_max",
        "international": "international_max",
        "per_mile":      "mileage_per_mile",
    }
    max_val = limits.get(limit_map[unit]) if unit in limit_map else None

    if max_val is None:
        return f"No limit found for category='{category}', unit='{unit}'."

    within = amount <= max_val
    excess = round(max(0.0, amount - max_val), 2)
    return f"Category: {category} | Claimed: ${amount} | Limit: ${max_val} | Within limit: {within} | Excess: ${excess}"


@tool
def receipt_validator(expenses: list) -> str:
    """
    Check which expenses are missing required receipts.
    Receipts required for any single expense above $25 (except per-diem meals).
    """
    missing = []
    for item in expenses:
        if item.get("category") == "meals":
            continue
        if item.get("amount", 0) > 25 and not item.get("has_receipt", False):
            missing.append(f"'{item.get('description', 'unknown')}' (${item.get('amount')})")

    if not missing:
        return "All required receipts are present."
    return f"Missing receipts for: {', '.join(missing)}. These items cannot be reimbursed per §1."


@tool
def duplicate_detector(employee_id: str, start_date: str, category: str) -> str:
    """Check if a claim from this employee for this travel date already exists."""
    key = f"{employee_id}-{start_date}"
    existing = _submitted_claims.get(key)
    if existing:
        return f"DUPLICATE DETECTED: Claim {existing} already exists for {employee_id} on {start_date}."
    return f"No duplicate found for employee {employee_id} on {start_date}."


@tool
def approval_threshold(total_amount: float) -> str:
    """Return the required approval tier for a given claim total."""
    tier = get_approval_tier(total_amount)
    return (
        f"Total: ${total_amount} | Tier: {tier['name']} | "
        f"Required approver: {tier['required_approver']} | "
        f"Policy ref: {tier['policy_ref']}"
    )
