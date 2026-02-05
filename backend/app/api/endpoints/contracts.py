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
from backend.services.contract_service import ContractService

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


@router.post("/parse")
async def parse_contract(contract_url: str = Query(..., description="URL of the contract to parse")):
    """
    Parse a contract from its URL.
    
    This endpoint uses the contract parser to extract details from a zakupki.gov.ru contract URL.
    """
    logger.info(f"Parsing contract: {contract_url}")
    
    try:
        # Initialize parser and service
        parser = ContractParser()
        service = ContractService()
        
        # Parse the contract
        parsed_data = await parser.parse_contract(contract_url)
        
        # Process with service for standardized output
        processed_data = await service.process_contract(contract_url)
        
        # Return combined data
        return {
            "success": True,
            "contract_url": contract_url,
            "parsed_data": parsed_data,
            "processed_data": processed_data,
            "summary": service.get_contract_summary(processed_data)
        }
        
    except Exception as e:
        logger.error(f"Failed to parse contract {contract_url}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse contract: {str(e)}"
        )


@router.post("/parse/batch")
async def parse_contracts_batch(contract_urls: List[str]):
    """
    Parse multiple contracts in batch.
    
    Args:
        contract_urls: List of contract URLs to parse
    """
    logger.info(f"Parsing {len(contract_urls)} contracts in batch")
    
    try:
        service = ContractService()
        
        # Process all contracts
        results = await service.process_multiple_contracts(contract_urls)
        
        # Calculate statistics
        successful = [r for r in results if r.get("processing_success")]
        failed = [r for r in results if not r.get("processing_success")]
        
        return {
            "success": True,
            "total_contracts": len(contract_urls),
            "successful_parses": len(successful),
            "failed_parses": len(failed),
            "results": results,
            "statistics": {
                "contracts_2025_plus": len([r for r in successful if r.get("is_2025_plus")]),
                "total_attachments": sum(r.get("attachments_count", 0) for r in successful),
                "contracts_with_printed_form": len([r for r in successful if r.get("has_printed_form")]),
                "total_unit_prices": sum(r.get("unit_prices_count", 0) for r in successful)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to parse contracts batch: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse contracts: {str(e)}"
        )