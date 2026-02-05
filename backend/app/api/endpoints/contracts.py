"""
Contract-related endpoints.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

from backend.services.parser.contract import ContractParser

router = APIRouter()
logger = logging.getLogger(__name__)


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


class ContractParseResult(BaseModel):
    """Contract parsing result model."""
    reestr_number: str
    contract_url: str
    common_info: Dict[str, Any]
    specification: List[Dict[str, Any]]
    attachments: Dict[str, Any]
    is_2025_plus: bool
    unit_prices: List[Dict[str, Any]]
    parsed_at: str


@router.post("/parse", response_model=ContractParseResult)
async def parse_contract(contract_url: str):
    """
    Parse contract data from zakupki.gov.ru URL.
    
    Args:
        contract_url: URL to contract card on zakupki.gov.ru
        
    Returns:
        Parsed contract data
    """
    try:
        async with ContractParser() as parser:
            parsed_data = await parser.parse_contract(contract_url)
            return ContractParseResult(**parsed_data)
    except Exception as e:
        logger.error(f"Failed to parse contract {contract_url}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse contract: {str(e)}"
        )


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