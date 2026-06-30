import json
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE, MANUAL_REVIEW_THRESHOLD
from src.models import ClaimInput, ReimbursementDecision, AuditStep
from src.tools import policy_lookup, limit_checker, receipt_validator, duplicate_detector, approval_threshold
from src.audit import AuditLogger

SYSTEM_PROMPT = """You are a Travel Reimbursement Approval Agent for HCL Corp.
Evaluate the claim and tool results. Return a JSON decision.

DECISION TYPES:
- Approve: all items within limits, receipts present, on time, no duplicate.
- Partially Approve: some items exceed limits or missing receipts.
- Reject: submitted >30 days late, duplicate, or business class without VP approval.
- Manual Review: ambiguous, >50% undocumented, or confidence < 0.6.

CALCULATION RULES:
- approved_amount: The sum of all approved portions of expenses.
- rejected_amount: The sum of all deducted/rejected amounts.
- total_claimed = approved_amount + rejected_amount.
- For each deduction, specify: claimed_amount, approved_amount (claimed - deducted), and deducted_amount.
- For fully rejected items (e.g. missing receipts > $25), deducted_amount equals claimed_amount, and approved_amount is 0.0.

DEDUCTION RULES:
- Hotel >$200/night: deduct (rate - 200) * nights
- Meals >$75/day: deduct excess
- Rideshare/taxi >$50/trip: deduct excess
- Missing receipt on item >$25: reject that item entirely (approved = 0)
- Alcohol: reject entirely
- Personal entertainment: reject entirely
- Business class without VP approval: reject flight entirely

CONFIDENCE: 0.9-1.0 clean claim | 0.7-0.89 minor deductions | 0.5-0.69 significant issues | <0.5 always Manual Review

Return ONLY valid JSON:
{"claim_id":"str","decision":"Approve|Partially Approve|Reject|Manual Review","approved_amount":0.0,"rejected_amount":0.0,"deductions":[{"expense_description":"str","claimed_amount":0.0,"approved_amount":0.0,"deducted_amount":0.0,"reason":"str","policy_ref":"str"}],"missing_documents":["str"],"policy_references":["str"],"required_approver":"Automated|Direct Manager|Vice President","confidence":0.0,"explanation":"str","routed_to":"Automated|Manager Approval Queue|VP Approval Queue|Manual Review Queue"}"""


def _days_since(travel_end: str, submission: str) -> int:
    try:
        end = datetime.strptime(travel_end, "%Y-%m-%d").date()
        sub = datetime.strptime(submission, "%Y-%m-%d").date()
        return (sub - end).days
    except Exception:
        return -1


def _run_tools(claim: ClaimInput, audit: AuditLogger) -> dict:
    results = {}

    dup_out = duplicate_detector.invoke({
        "employee_id": claim.employee.id,
        "start_date": claim.travel.start_date,
        "category": "all",
    })
    audit.log("duplicate_detector", f"employee_id={claim.employee.id}, start_date={claim.travel.start_date}", dup_out)
    results["duplicate_check"] = dup_out

    days_late = _days_since(claim.travel.end_date, claim.travel.submission_date)
    results["submission_days_after_travel"] = days_late
    results["submission_on_time"] = days_late <= 30
    audit.log(
        "submission_checker",
        f"end={claim.travel.end_date}, submitted={claim.travel.submission_date}",
        f"Submitted {days_late} days after travel end. On time: {days_late <= 30}",
    )

    categories = list(set(e.category for e in claim.expenses))
    policy_out = policy_lookup.invoke({"query": " ".join(categories)})
    audit.log("policy_lookup", f"query={' '.join(categories)}", policy_out[:200])
    results["policy_context"] = policy_out

    limit_results = []
    for exp in claim.expenses:
        cat, amt = exp.category, exp.amount

        if cat == "flight":
            unit = exp.type if exp.type in ("domestic", "international") else "domestic"
            out = limit_checker.invoke({"category": "flight", "amount": amt, "unit": unit})
            audit.log("limit_checker", f"flight, {amt}, {unit}", out)

        elif cat == "hotel":
            per_night = exp.per_night or (amt / exp.nights if exp.nights else amt)
            out = limit_checker.invoke({"category": "hotel", "amount": per_night, "unit": "per_night"})
            audit.log("limit_checker", f"hotel, per_night={per_night}", out)

        elif cat == "meals":
            per_day = amt / exp.days if exp.days else amt
            out = limit_checker.invoke({"category": "meals", "amount": per_day, "unit": "per_day"})
            audit.log("limit_checker", f"meals, per_day={per_day}", out)

        elif cat == "ground_transport":
            out = limit_checker.invoke({"category": "ground_transport", "amount": amt, "unit": "per_trip"})
            audit.log("limit_checker", f"ground_transport, per_trip={amt}", out)

        else:
            out = f"No limit rule for category '{cat}' — flag for review."

        limit_results.append({"expense": exp.description, "result": out})

    results["limit_checks"] = limit_results

    expenses_list = [e.model_dump() for e in claim.expenses]
    receipt_out = receipt_validator.invoke({"expenses": expenses_list})
    audit.log("receipt_validator", f"{len(expenses_list)} expenses", receipt_out)
    results["receipt_check"] = receipt_out

    threshold_out = approval_threshold.invoke({"total_amount": claim.total_claimed})
    audit.log("approval_threshold", f"total_claimed={claim.total_claimed}", threshold_out)
    results["approval_threshold"] = threshold_out

    return results


def _build_context(claim: ClaimInput, tool_results: dict) -> str:
    limit_summary = "\n".join(
        f"  - {lr['expense']}: {lr['result']}"
        for lr in tool_results.get("limit_checks", [])
    )
    return f"""CLAIM:
{claim.model_dump_json(indent=None)}

TOOL RESULTS:
1. Duplicate: {tool_results.get('duplicate_check')}
2. Submission: {tool_results.get('submission_days_after_travel')} days after travel. On time: {tool_results.get('submission_on_time')}
3. Policy: {tool_results.get('policy_context', '')[:300]}
4. Limits:
{limit_summary}
5. Receipts: {tool_results.get('receipt_check')}
6. Approval: {tool_results.get('approval_threshold')}

Return JSON decision for claim_id={claim.claim_id}."""


def _parse_decision(raw: str, claim: ClaimInput, audit_steps: list[AuditStep]) -> ReimbursementDecision:
    text = raw.strip()
    if "```" in text:
        lines, cleaned, in_block = text.split("\n"), [], False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            cleaned.append(line)
        text = "\n".join(cleaned).strip()

    start, end = text.find("{"), text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    try:
        data = json.loads(text)
        data["claim_id"] = claim.claim_id
        data["audit_trail"] = [s.model_dump() for s in audit_steps]
        decision = ReimbursementDecision(**data)

        # Enforce safety assertions and policy compliance programmatically
        days_late = _days_since(claim.travel.end_date, claim.travel.submission_date)
        if days_late > 30:
            decision.decision = "Reject"

        missing_sum = sum(
            exp.amount for exp in claim.expenses
            if exp.category != "meals" and exp.amount > 25 and not exp.has_receipt
        )
        if missing_sum > 0.5 * claim.total_claimed:
            decision.decision = "Manual Review"
            decision.routed_to = "Manual Review Queue"

        if decision.confidence < MANUAL_REVIEW_THRESHOLD:
            decision.decision = "Manual Review"
            decision.routed_to = "Manual Review Queue"

        return decision
    except Exception as e:
        return ReimbursementDecision(
            claim_id=claim.claim_id,
            decision="Manual Review",
            approved_amount=0.0,
            rejected_amount=0.0,
            missing_documents=[f"Parse error: {str(e)[:120]}"],
            policy_references=["§7. Incomplete Claims"],
            required_approver="Manual Reviewer",
            confidence=0.0,
            explanation=f"Could not parse agent output. Routed to manual review. Raw: {raw[:200]}",
            routed_to="Manual Review Queue",
            audit_trail=audit_steps,
        )


def evaluate_claim(claim: ClaimInput) -> ReimbursementDecision:
    audit = AuditLogger()
    tool_results = _run_tools(claim, audit)

    llm = ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=LLM_TEMPERATURE)
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=_build_context(claim, tool_results)),
    ])

    return _parse_decision(response.content, claim, audit.steps())
