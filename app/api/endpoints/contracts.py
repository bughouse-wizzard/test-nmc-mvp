from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    ai_score: int = Field(..., ge=0, le=100, description="AI score 0-100")
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
    weight: int = 1


@router.get("/{contract_id}", response_model=ContractResult)
async def get_contract(contract_id: UUID):
    """Get contract by ID."""
    # TODO: Implement actual contract retrieval
    raise HTTPException(status_code=404, detail="Contract not found")


@router.get("/{contract_id}/comparison", response_model=List[SpecComparisonRow])
async def get_contract_comparison(contract_id: UUID):
    """Get contract specification comparison."""
    # TODO: Implement actual comparison retrieval
    return []
