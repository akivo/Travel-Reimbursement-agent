import json
import argparse
from pathlib import Path
from src.models import ClaimInput, ReimbursementDecision
from src.agent import evaluate_claim
from src.audit import format_audit_trail

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
ORANGE = "\033[38;5;208m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

DECISION_COLOR = {
    "Approve": GREEN,
    "Partially Approve": YELLOW,
    "Reject": RED,
    "Manual Review": ORANGE,
}

DECISION_ICON = {
    "Approve": "[OK]",
    "Partially Approve": "[PARTIAL]",
    "Reject": "[REJECTED]",
    "Manual Review": "[MANUAL]",
}


def load_claim(path: str) -> ClaimInput:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("expected_decision", None)
    return ClaimInput(**data)


def print_decision(decision: ReimbursementDecision) -> None:
    color = DECISION_COLOR.get(decision.decision, RESET)
    icon = DECISION_ICON.get(decision.decision, "*")
    sep = "=" * 65
    sep2 = "-" * 65

    print("\n" + sep)
    print(f"  {BOLD}Claim ID:  {RESET}{decision.claim_id}")
    print(f"  {BOLD}Decision:  {RESET}{color}{BOLD}{icon} {decision.decision}{RESET}")
    print(f"  {BOLD}Confidence:{RESET} {decision.confidence * 100:.0f}%")
    print(sep2)
    print(f"  {BOLD}Approved Amount: {RESET} ${decision.approved_amount:,.2f}")
    print(f"  {BOLD}Rejected Amount: {RESET} ${decision.rejected_amount:,.2f}")
    print(f"  {BOLD}Required Approver:{RESET} {decision.required_approver}")
    print(f"  {BOLD}Routed To:       {RESET} {decision.routed_to}")

    if decision.deductions:
        print(f"\n  {BOLD}Deductions:{RESET}")
        for d in decision.deductions:
            print(f"    * {d.expense_description}: "
                  f"claimed ${d.claimed_amount:.2f} -> approved ${d.approved_amount:.2f} "
                  f"(deducted ${d.deducted_amount:.2f})")
            print(f"      Reason: {d.reason} [{d.policy_ref}]")

    if decision.missing_documents:
        print(f"\n  {BOLD}Missing Documents:{RESET}")
        for doc in decision.missing_documents:
            print(f"    * {doc}")

    if decision.policy_references:
        print(f"\n  {BOLD}Policy References:{RESET}")
        for ref in decision.policy_references:
            print(f"    * {ref}")

    print(f"\n  {BOLD}Explanation:{RESET}")
    print(f"    {decision.explanation}")

    if decision.audit_trail:
        print(format_audit_trail(decision.audit_trail))

    print(sep + "\n")


def save_output(decision: ReimbursementDecision, claim_path: str) -> None:
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    claim_name = Path(claim_path).stem
    output_file = outputs_dir / f"{claim_name}_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(decision.model_dump_json(indent=2))
    print(f"  {CYAN}[SAVED] Output saved -> {output_file}{RESET}\n")


def run_claim(claim_path: str, save: bool = False) -> ReimbursementDecision:
    print(f"\n{CYAN}[>>] Loading claim: {claim_path}{RESET}")
    claim = load_claim(claim_path)
    print(f"{CYAN}[AI] Agent evaluating claim {claim.claim_id} ...{RESET}")
    decision = evaluate_claim(claim)
    print_decision(decision)
    if save:
        save_output(decision, claim_path)
    return decision


def main():
    parser = argparse.ArgumentParser(description="Travel Reimbursement Approval Agent CLI")
    parser.add_argument("--claim", type=str, help="Path to claim JSON file")
    parser.add_argument("--all", action="store_true", help="Run all sample claims")
    parser.add_argument("--save", action="store_true", help="Save decision to outputs/")
    args = parser.parse_args()

    if args.all:
        claims_dir = Path("data/claims")
        claim_files = sorted(claims_dir.glob("*.json"))
        if not claim_files:
            print("[ERROR] No claim files found in data/claims/")
            return
        for cf in claim_files:
            run_claim(str(cf), save=True)
    elif args.claim:
        run_claim(args.claim, save=args.save)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
