"""
CTC Budget Checker Tool API
FastAPI endpoint to check if candidate's expected CTC is within budget
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CTC Budget Checker API",
    description="API to check if candidate's expected CTC is within company budget",
    version="1.0.0"
)

# Enable CORS for Ultravox to call this endpoint
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class CTCRequest(BaseModel):
    """Request model for CTC budget check"""
    expected_ctc: str = Field(..., description="Candidate's expected CTC in LPA (e.g., '45', '85')")
    max_budget: str = Field(..., description="Maximum budget for position in LPA")

    class Config:
        schema_extra = {
            "example": {
                "expected_ctc": "85",
                "max_budget": "90"
            }
        }


class CTCResponse(BaseModel):
    """Response model for CTC budget check"""
    result: str = Field(..., description="Result: 'Within budget', 'Above budget', or 'Error'")
    message: str = Field(..., description="Detailed message about the result")
    error: Optional[str] = Field(None, description="Error type if result is 'Error'")

    class Config:
        schema_extra = {
            "example": {
                "result": "Within budget",
                "message": "Expected CTC of 85.0 LPA is within the maximum budget of 90.0 LPA"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status")


@app.post("/check-ctc", response_model=CTCResponse, summary="Check CTC Budget")
async def check_ctc(request: CTCRequest) -> CTCResponse:
    """
    Check if candidate's expected CTC is within company budget.

    Returns:
    - **Within budget**: If expected CTC ≤ max budget
    - **Above budget**: If expected CTC > max budget
    - **Error**: If validation fails (with graceful degradation message)
    """
    try:
        expected_ctc_str = request.expected_ctc.strip()
        max_budget_str = request.max_budget.strip()

        # Validate inputs are not empty
        if not expected_ctc_str or not max_budget_str:
            return CTCResponse(
                result="Error",
                error="Missing parameters",
                message="Both expected_ctc and max_budget are required. Proceeding without budget check."
            )

        # Convert to float for comparison
        try:
            expected_ctc = float(expected_ctc_str)
            max_budget = float(max_budget_str)
        except ValueError:
            return CTCResponse(
                result="Error",
                error="Invalid number format",
                message="expected_ctc and max_budget must be valid numbers. Proceeding without budget check."
            )

        # Validate reasonable ranges (0-200 LPA)
        if expected_ctc < 0 or expected_ctc > 200 or max_budget < 0 or max_budget > 200:
            return CTCResponse(
                result="Error",
                error="Invalid range",
                message="CTC values must be between 0 and 200 LPA. Proceeding without budget check."
            )

        # Check budget
        if expected_ctc <= max_budget:
            result = "Within budget"
            message = f"Expected CTC of {expected_ctc} LPA is within the maximum budget of {max_budget} LPA"
        else:
            result = "Above budget"
            message = f"Expected CTC of {expected_ctc} LPA is above the maximum budget of {max_budget} LPA"

        return CTCResponse(result=result, message=message)

    except Exception as e:
        # Log the error but return 200 with error info for graceful degradation
        logger.error(f"Unexpected error in check_ctc: {str(e)}")
        return CTCResponse(
            result="Error",
            error="Server error",
            message=f"An unexpected error occurred: {str(e)}. Proceeding without budget check."
        )


@app.get("/health", response_model=HealthResponse, summary="Health Check")
async def health() -> HealthResponse:
    """
    Health check endpoint to verify service is running.
    """
    return HealthResponse(status="healthy")


@app.get("/", summary="Root")
async def root():
    """
    Root endpoint - redirects to API documentation.
    """
    return {
        "message": "CTC Budget Checker API",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    import os

    # Use PORT from environment (for EasyPanel/Railway/Render) or default to 8000 for local dev
    port = int(os.environ.get("PORT", 8000))

    # Run with uvicorn
    uvicorn.run(
        "ctc_tool_api:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )
