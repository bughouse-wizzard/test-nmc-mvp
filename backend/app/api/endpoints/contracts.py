"""
Contract-related endpoints.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()


class ContractResult(BaseModel):
    """Contract result model."""
    id: UUID
    search_id: UUID
    reestr_number: str
    contract_url: str
    sign_date: datetime
    unit_price: Optional[float] = None
    currency: str = "RUB"
    match_type: str = Field(..., description="IDENTICAL|HOMOGENEOUS|NO_MATCH")
    ai_score: int = Field(..., ge=0, le=100)
    manufacturer_target: Optional[str] = None
    manufacturer_found: Optional[str] = None
    manufacturer_match: Optional[bool] = None
    is_2025_plus: bool = False
    accepted_for_nmc: bool = False
    created_at: datetime


class SpecComparisonRow(BaseModel):
    """Specification comparison row model."""
    name: str
    target_value: str
    actual_value: str
    match_status: str = Field(..., description="MATCH|DIFF|UNKNOWN")
    weight: int = Field(1, ge=1, le=10)


@router.get("/{contract_id}", response_model=ContractResult)
async def get_contract(contract_id: UUID):
    """
    Get details of a specific contract.
    """
    # TODO: Implement actual retrieval logic
    raise HTTPException(status_code=404, detail="Contract not found")


@router.get("/{contract_id}/comparison")
async def get_contract_comparison(contract_id: UUID):
    """
    Get detailed comparison for a specific contract.
    """
    # TODO: Implement actual comparison retrieval
    return {
        "contract_id": contract_id,
        "comparison_rows": [],
        "summary": {
            "total_rows": 0,
            "matched_rows": 0,
            "different_rows": 0,
            "match_percentage": 0.0
        }
    }


@router.get("/")
async def list_contracts(
    search_id: Optional[UUID] = None,
    match_type: Optional[str] = Query(None, description="Filter by match type"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum AI score"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List contracts with optional filtering.
    """
    # TODO: Implement actual listing logic
    return {
        "contracts": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }