"""
Search endpoints for contract search and NMCK calculation.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()


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
    # TODO: Implement actual search logic
    # For now, return a mock response
    from uuid import uuid4
    from datetime import datetime
    
    return SearchResponse(
        id=uuid4(),
        status="RUNNING",
        created_at=datetime.now(),
        object_name=request.object_name,
        ktru_code=request.ktru_code,
        found_total=0,
        processed_count=0,
        nmc_value=None
    )


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