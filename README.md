# Travel Reimbursement Approval Agent

An AI-driven agent service to evaluate employee travel reimbursement claims against corporate travel policies. The system processes claims submitted as JSON, executes validation checks via structured tools, evaluates policy compliance, and returns a structured approval decision and audit trail.

---

## Architecture Overview

The system uses a pipeline pattern combining deterministic policy verification tools with LLM-based policy synthesis:

```
                      [ Claim JSON ]
                             │
                             ▼
         [ Rule Evaluation & Tool Orchestration ]
     ┌───────────────────────┼──────────────────────┐
     │                       │                      │
[Duplicate Check]     [Policy Excerpts]     [Limit Verification]
     │                       │                      │
     └───────────────────────┼──────────────────────┘
                             │
                             ▼
                [ LLM Decision Synthesis ]
              ( llama-3.1-8b-instant @ Groq )
                             │
                             ▼
               [ ReimbursementDecision JSON ]
              ( Validated via Pydantic v2 )
```

1. **Deterministic Tool Pipeline**: 
   - `duplicate_detector`: Compares the claim against previously submitted claims.
   - `submission_checker`: Validates if the claim was submitted within the 30-day policy window.
   - `policy_lookup`: Fetches travel policy clauses relevant to the expense categories.
   - `limit_checker`: Validates line items against category caps (e.g. $200/night hotel limits).
   - `receipt_validator`: Flags missing receipts for expenses exceeding $25.
   - `approval_threshold`: Maps final approved amounts to required organizational approval tiers.
2. **LLM Decision Synthesis**: The pre-computed tool outputs are formatted into a single context prompt and sent to the LLM. The LLM performs the final compliance reasoning, calculates deductions, sets a confidence score, and returns a structured output.
3. **Pydantic Validation**: Enforces literal constraints on the output fields to guarantee stable down-stream integration.

---

## Tech Stack

- **Core**: Python 3.11+
- **Agent Framework**: LangChain (for tool definitions & model interactions)
- **Structured Schema**: Pydantic v2
- **Model Inference**: Groq Cloud (`llama-3.1-8b-instant`)
- **API Framework**: FastAPI
- **Web Interface**: HTML5 / CSS / Vanilla JavaScript
- **Currency**: Indian Rupee (₹ INR) — all policy limits and claim amounts are in INR

---

## Directory Structure

```
tr-agent/
├── requirements.txt            # Package dependencies
├── .env                        # Local environment settings (GROQ_API_KEY)
├── main.py                     # CLI Entrypoint
├── api.py                      # FastAPI Web API
├── data/
│   ├── policy.md               # Markdown corporate policy
│   ├── limits.json             # Expense limits schema
│   ├── approval_matrix.json    # Approval escalation limits
│   └── claims/                 # Mock claim JSON payloads
├── src/
│   ├── __init__.py
│   ├── config.py               # Settings and configuration
│   ├── models.py               # Pydantic schemas (input & output)
│   ├── policy_store.py         # Parsing and local policy search
│   ├── tools.py                # LangChain tool implementations
│   ├── agent.py                # Orchestration and LLM reasoning
│   └── audit.py                # Audit log tracking
├── tests/
│   ├── conftest.py             # Pytest runtime configuration
│   └── test_claims.py          # Unit & Integration test suite
├── outputs/                    # Output decision JSONs saved from CLI
└── ui/
    └── index.html              # Frontend user interface
```

---

## Getting Started

### 1. Environment Setup

Clone this repository, navigate to the project directory, and configure a virtual environment:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root containing your Groq API key:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

---

## Usage

### CLI Execution

You can run individual claims or run all mock claims using the command-line utility.

```bash
# Run all mock claims and save outputs
python main.py --all

# Run a single claim with console output
python main.py --claim data/claims/claim_001_approved.json

# Run a single claim and save output to outputs/
python main.py --claim data/claims/claim_002_partial.json --save
```

### Web API and UI

FastAPI hosts the core agent evaluator endpoints and lists the mock claims.

1. **Start the API Server**:
   ```bash
   uvicorn api:app --reload --port 8000
   ```
2. **Access Swagger Documentation**: Open `http://localhost:8000/docs` in your browser.
3. **Open the Web Interface**: Simply open `ui/index.html` in your web browser. The frontend makes asynchronous requests to the FastAPI backend to run claim analysis.

---

## Testing

Pytest is used for tool unit tests and end-to-end integration tests:

```bash
# Run all tests
pytest tests/ -v

# Run tool tests only (offline, no LLM calls)
pytest tests/ -v -k "TestTools"

# Run a specific integration test
pytest tests/ -v -k "TestClaim001Approved"
```

---

## Sample Outputs

Four mock claims are included under `data/claims/`, covering all four decision paths. Generated output JSON files are saved under `outputs/` after running the CLI.

| Claim | Employee | Total Claimed | Scenario | Decision |
|---|---|---|---|---|
| CLM-001 | Riya Sharma | ₹26,350 | All expenses within limits, receipts present, on time | **Approve** |
| CLM-002 | Karan Patel | ₹51,650 | Hotel (₹11,500/night) and client dinner exceed policy limits | **Partially Approve** |
| CLM-003 | Vivek Nair | ₹4,02,500 | Business class without VP approval, submitted 71 days late | **Reject** |
| CLM-004 | Ananya Iyer | ₹14,720 | Missing receipts for personal car + homestay (79% undocumented) | **Manual Review** |

Each output JSON contains the full `ReimbursementDecision` schema including `decision`, `approved_amount`, `rejected_amount`, `deductions`, `policy_references`, `confidence`, `explanation`, and `audit_trail`.

---

## Assumptions and Limitations

### Assumptions
- All monetary amounts are in Indian Rupees (₹ INR), consistent with HCL Tech's India-based operations.
- Policy limits reflect standard Indian corporate travel policy: ₹8,000/night hotel, ₹1,500/day meals, ₹15,000 domestic flight cap.
- The travel policy document (`data/policy.md`) is the single source of truth. No external policy database is queried.
- The duplicate detector uses an in-memory registry. In production this would query a claims database.
- Groq free-tier API is used for inference. Rate limits may apply during high-volume testing.
- Submission deadline is calculated as calendar days (not business days) between travel end date and submission date.
- Meals are exempt from the receipt requirement (per-diem basis), consistent with common corporate policy.

### Simplifications
- The policy store uses keyword-based section matching rather than a vector embedding search (e.g. FAISS or Chroma). Sufficient for the scope of this prototype.
- No authentication or user session management is implemented on the API.
- The approval matrix is a static JSON file. In production this would be configurable per department or region.

### Known Gaps
- The agent does not handle multi-currency claims. All amounts are assumed to be pre-converted to USD.
- There is no persistent storage for submitted claims or audit logs. All data is in-memory per session.
- PDF or image receipt parsing is not implemented. Receipt presence is indicated by a boolean flag in the claim JSON.

### What I Would Improve Next
- Replace keyword policy search with a vector store (FAISS or Chroma) for more accurate retrieval on large policy documents.
- Add a persistent database (PostgreSQL) to store claim history and enable true duplicate detection across sessions.
- Implement streaming LLM responses so the UI shows the agent's reasoning in real time.
- Add role-based access control to the API so managers can view claims routed to their queue.
- Extend the test suite with property-based tests to validate agent behaviour across edge-case claim combinations.
