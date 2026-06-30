import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.models import ClaimInput, ReimbursementDecision
from src.agent import evaluate_claim

app = FastAPI(
    title="Travel Reimbursement Approval Agent API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Travel Reimbursement Approval Agent"}

@app.get("/sample-claims")
def list_sample_claims():
    claims_dir = Path("data/claims")
    if not claims_dir.exists():
        raise HTTPException(status_code=404, detail="claims directory not found")

    claims = []
    for f in sorted(claims_dir.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            claims.append({
                "filename": f.name,
                "claim_id": data.get("claim_id"),
                "employee_name": data.get("employee", {}).get("name"),
                "total_claimed": data.get("total_claimed"),
                "expected_decision": data.get("expected_decision"),
                "raw": data,
            })
        except Exception as e:
            continue
    return claims

@app.post("/evaluate-claim", response_model=ReimbursementDecision)
def evaluate(claim_data: ClaimInput):
    try:
        return evaluate_claim(claim_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate-claim/raw")
def evaluate_raw(claim_data: dict):
    claim_data.pop("expected_decision", None)
    try:
        claim = ClaimInput(**claim_data)
        decision = evaluate_claim(claim)
        return decision.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
