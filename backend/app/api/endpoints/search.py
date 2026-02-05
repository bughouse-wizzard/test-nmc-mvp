"""
Search endpoints for contract search and NMCK calculation.
"""
import asyncio
import logging
from typing import List, Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

from backend.services.contract_service import ContractService

router = APIRouter()
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    """Search request model."""
    object_name: str = Field(..., description="Name of the procurement object")
    ktru_code: str = Field(..., description="KTRU code")
    okpd2_code: Optional[str] = Field(None, description="OKPD2 code")
    customer_region: str = Field("СЗФО", description="Customer region")
    law: str = Field("44-ФЗ", description="Procurement law")
    date_from: datetime = Field(..., description="Start date for search")
    date_to: datetime = Field(..., description="End date for search")
    execution_statuses: List[str] = Field(["Исполнение завершено"], description="Execution statuses")
    limit_contracts: int = Field(30, description="Maximum number of contracts to process")
    characteristics_text: Optional[str] = Field(None, description="Text description of characteristics")
    manufacturer: Optional[str] = Field(None, description="Target manufacturer")


class SearchResponse(BaseModel):
    """Search response model."""
    id: UUID
    status: str
    created_at: datetime
    object_name: str
    ktru_code: str
    found_total: Optional[int] = None
    processed_count: int = 0
    nmc_value: Optional[float] = None


@router.post("/", response_model=SearchResponse)
async def create_search(request: SearchRequest, background_tasks: BackgroundTasks):
    """
    Create a new search for contracts.
    
    This endpoint initiates a search for contracts based on the provided criteria.
    The search runs in the background.
    """
    search_id = uuid4()
    
    # Start background task for contract processing
    background_tasks.add_task(
        process_contracts_background,
        search_id,
        request
    )
    
    return SearchResponse(
        id=search_id,
        status="RUNNING",
        created_at=datetime.now(),
        object_name=request.object_name,
        ktru_code=request.ktru_code,
        found_total=0,
        processed_count=0,
        nmc_value=None
    )


async def process_contracts_background(search_id: UUID, request: SearchRequest):
    """
    Background task for processing contracts.
    
    Args:
        search_id: Search request ID
        request: Search request data
    """
    logger.info(f"Starting background processing for search {search_id}")
    
    try:
        # Initialize contract service
        contract_service = ContractService()
        
        # TODO: In a real implementation, this would fetch actual contract URLs
        # from zakupki.gov.ru based on search criteria
        # For now, use mock/test URLs
        mock_contract_urls = [
            "https://zakupki.gov.ru/contractCard/common-info.html?reestrNumber=1234567890",
            "https://zakupki.gov.ru/contractCard/common-info.html?reestrNumber=9876543210",
            "https://zakupki.gov.ru/contractCard/common-info.html?reestrNumber=5555555555"
        ]
        
        # Process contracts
        logger.info(f"Processing {len(mock_contract_urls)} contracts for search {search_id}")
        processed_contracts = await contract_service.process_multiple_contracts(mock_contract_urls)
        
        # Filter contracts by year (last 3 years as per requirements)
        current_year = datetime.now().year
        filtered_contracts = contract_service.filter_contracts_by_year(
            processed_contracts,
            min_year=current_year - 3
        )
        
        # Calculate statistics
        successful_contracts = [c for c in filtered_contracts if c.get("processing_success")]
        
        logger.info(f"Search {search_id} completed: "
                   f"processed {len(processed_contracts)} contracts, "
                   f"{len(successful_contracts)} successful")
        
        # TODO: Store results in database
        # TODO: Calculate NMCK value
        
    except Exception as e:
        logger.error(f"Background processing failed for search {search_id}: {e}")


@router.get("/", response_model=List[SearchResponse])
async def list_searches(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List all search requests.
    """
    # TODO: Implement actual listing logic
    return []


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(search_id: UUID):
    """
    Get details of a specific search.
    """
    # TODO: Implement actual retrieval logic
    raise HTTPException(status_code=404, detail="Search not found")


@router.post("/{search_id}/stop")
async def stop_search(search_id: UUID):
    """
    Stop a running search.
    """
    # TODO: Implement actual stop logic
    return {"message": f"Search {search_id} stopped successfully"}


@router.get("/{search_id}/results")
async def get_search_results(
    search_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Get results of a specific search.
    """
    # TODO: Implement actual results retrieval
    return {
        "search_id": search_id,
        "results": [],
        "total": 0
    }


@router.get("/{search_id}/report")
async def download_report(search_id: UUID):
    """
    Download a report for a specific search.
    """
    # TODO: Implement report generation
    raise HTTPException(status_code=404, detail="Report not available")