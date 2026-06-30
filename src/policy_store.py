import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "policy.md", "r", encoding="utf-8") as f:
    _policy_text = f.read()

with open(DATA_DIR / "limits.json", "r") as f:
    LIMITS = json.load(f)

with open(DATA_DIR / "approval_matrix.json", "r") as f:
    APPROVAL_MATRIX = json.load(f)


def search_policy(query: str) -> str:
    query_lower = query.lower()
    sections = _policy_text.split("##")
    matches = [
        s.strip() for s in sections
        if any(word in s.lower() for word in query_lower.split())
    ]
    if not matches:
        return "No specific policy found. Refer to general rules in §1."
    return "\n\n---\n\n".join(matches[:2])


def get_limit(category: str) -> dict:
    return LIMITS.get(category, LIMITS.get("global", {}))


def get_approval_tier(total_amount: float) -> dict:
    for tier in APPROVAL_MATRIX["tiers"]:
        if tier["min_amount"] <= total_amount <= tier["max_amount"]:
            return tier
    return APPROVAL_MATRIX["tiers"][-1]
