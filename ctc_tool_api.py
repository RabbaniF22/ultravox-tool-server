"""
CTC Budget Checker Tool API
FastAPI endpoint to check if candidate's expected CTC is within budget.

✅ Works with:
- Direct callers sending top-level max_budget / maxBudget
- Millis payloads where budget is inside metadata.max_budget / metadata.maxBudget

🔒 Security:
- Never returns the numeric budget in the response (prevents budget leakage via LLM/tool output).
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(
    title="CTC Budget Checker API",
    description="API to check if candidate's expected CTC is within company budget",
    version="1.1.0",
)

# Enable CORS (adjust allow_origins to your domains in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Models
# ------------------------------------------------------------
class Metadata(BaseModel):
    """
    Millis-style metadata container.
    Millis may send snake_case keys (max_budget) or camelCase keys (maxBudget).
    """
    max_budget: Optional[str] = Field(default=None, alias="maxBudget")
    # Allow additional metadata keys without failing validation
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class CTCRequest(BaseModel):
    """
    Request model for CTC budget check.

    Supports:
    - expected_ctc / expectedCtc
    - max_budget / maxBudget (top-level direct call)
    - metadata.max_budget / metadata.maxBudget (Millis metadata)
    """
    expected_ctc: str = Field(
        ...,
        alias="expectedCtc",
        description="Candidate's expected CTC in LPA (e.g., '45', '85')",
    )

    # Optional because Millis may not send it at top-level; we will also read from metadata.
    max_budget: Optional[str] = Field(
        default=None,
        alias="maxBudget",
        description="Maximum budget for position in LPA (top-level direct calls)",
    )

    # Millis can send metadata; we parse it and extract budget from there if needed.
    metadata: Optional[Metadata] = Field(
        default=None,
        description="Optional Millis call metadata; may contain max_budget/maxBudget",
    )

    # Accept both snake_case and camelCase keys from external callers.
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "expected_ctc": "85",
                "metadata": {"max_budget": "90"},
            }
        },
    )


class CTCResponse(BaseModel):
    """Response model for CTC budget check"""
    result: str = Field(..., description="Result: 'Within budget', 'Above budget', or 'Error'")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "result": "Above budget",
            }
        }
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _extract_max_budget(req: CTCRequest) -> Optional[str]:
    """
    Extract max_budget from:
    1) req.max_budget (top-level)
    2) req.metadata.max_budget (Millis metadata)
    """
    if req.max_budget and req.max_budget.strip():
        return req.max_budget.strip()

    if req.metadata:
        # req.metadata.max_budget covers both alias maxBudget and name max_budget due to ConfigDict(populate_by_name=True)
        if req.metadata.max_budget and req.metadata.max_budget.strip():
            return req.metadata.max_budget.strip()

        # Extra safety if metadata came in as raw dict under extra fields
        # (shouldn't be needed, but avoids surprises)
        if isinstance(req.metadata, dict):
            v = req.metadata.get("max_budget") or req.metadata.get("maxBudget")
            if isinstance(v, str) and v.strip():
                return v.strip()

    # Also check if payload had "metadata" as a dict but Pydantic couldn't parse (rare)
    raw_meta = getattr(req, "metadata", None)
    if isinstance(raw_meta, dict):
        v = raw_meta.get("max_budget") or raw_meta.get("maxBudget")
        if isinstance(v, str) and v.strip():
            return v.strip()

    return None


def _parse_lpa(value: str) -> Optional[float]:
    """
    Parse LPA number from a string.

    Accepts:
    - "75"
    - "75.5"
    - "75 LPA"
    - "75lpa"
    - "₹75" (will strip non-numeric edges)

    Returns float or None if invalid.
    """
    if not value:
        return None

    s = value.strip().lower()
    # Remove common noise
    for token in ["lpa", "₹", "rs", "inr", ","]:
        s = s.replace(token, "")

    # Keep only digits, dot, and minus (just in case)
    cleaned = "".join(ch for ch in s if (ch.isdigit() or ch in ".-"))
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@app.post("/check-ctc", response_model=CTCResponse, summary="Check CTC Budget")
async def check_ctc(request: CTCRequest) -> CTCResponse:
    """
    Check if candidate's expected CTC is within company budget.

    Returns:
    - **Within budget**: If expected CTC ≤ max budget
    - **Above budget**: If expected CTC > max budget
    - **Error**: If validation fails

    🔒 Returns only the result field and does NOT reveal the budget number.
    """
    try:
        expected_ctc_str = (request.expected_ctc or "").strip()
        max_budget_str = _extract_max_budget(request) or ""

        # Validate inputs are not empty
        if not expected_ctc_str or not max_budget_str:
            return CTCResponse(result="Error")

        expected_ctc = _parse_lpa(expected_ctc_str)
        max_budget = _parse_lpa(max_budget_str)

        if expected_ctc is None or max_budget is None:
            return CTCResponse(result="Error")

        # Validate reasonable ranges (0-200 LPA)
        if expected_ctc < 0 or expected_ctc > 200 or max_budget < 0 or max_budget > 200:
            return CTCResponse(result="Error")

        # Budget check (NO budget leak in response)
        if expected_ctc <= max_budget:
            return CTCResponse(result="Within budget")

        return CTCResponse(result="Above budget")

    except Exception as e:
        logger.exception("Unexpected error in check_ctc")
        return CTCResponse(result="Error")


@app.get("/health", response_model=HealthResponse, summary="Health Check")
async def health() -> HealthResponse:
    """Health check endpoint to verify service is running."""
    return HealthResponse(status="healthy")


@app.get("/", summary="Root")
async def root() -> Dict[str, str]:
    """Root endpoint - points to docs and health."""
    return {"message": "CTC Budget Checker API", "docs": "/docs", "health": "/health"}


# ------------------------------------------------------------
# Local dev entrypoint
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "ctc_tool_api:app",  # <-- rename file to ctc_tool_api.py OR update this string
        host="0.0.0.0",
        port=port,
        reload=True,  # dev only
        log_level="info",
    )
