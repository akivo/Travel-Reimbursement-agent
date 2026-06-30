from pydantic import BaseModel, Field
from typing import Literal, Optional


class ExpenseItem(BaseModel):
    category: str
    description: str
    amount: float
    has_receipt: bool
    vendor: str
    date: str
    type: Optional[str] = None
    nights: Optional[int] = None
    per_night: Optional[float] = None
    days: Optional[int] = None
    miles: Optional[float] = None
    note: Optional[str] = None


class Employee(BaseModel):
    id: str
    name: str
    department: str
    manager: str


class TravelInfo(BaseModel):
    purpose: str
    destination: str
    start_date: str
    end_date: str
    submission_date: str


class ClaimInput(BaseModel):
    claim_id: str
    employee: Employee
    travel: TravelInfo
    expenses: list[ExpenseItem]
    total_claimed: float


class Deduction(BaseModel):
    expense_description: str
    claimed_amount: float
    approved_amount: float
    deducted_amount: float
    reason: str
    policy_ref: str


class AuditStep(BaseModel):
    step: int
    tool_called: str
    input_summary: str
    output_summary: str


class ReimbursementDecision(BaseModel):
    claim_id: str
    decision: Literal["Approve", "Partially Approve", "Reject", "Manual Review"]
    approved_amount: float
    rejected_amount: float
    deductions: list[Deduction] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    policy_references: list[str] = Field(default_factory=list)
    required_approver: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    routed_to: str
    audit_trail: list[AuditStep] = Field(default_factory=list)
