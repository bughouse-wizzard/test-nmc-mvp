"""
Search endpoints for contract search and NMCK calculation.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.models import SearchRequest as SearchRequestModel, SearchStatus, InputSource, ContractResult as ContractResultModel
from backend.app.db import get_db

router = APIRouter()


# Pydantic schemas
class SearchRequestCreate(BaseModel):
    """Search request creation model."""
    object_name: str = Field(..., description="Name of the procurement object")
    ktru_code: str = Field(..., description="KTRU code")
    okpd2_code: Optional[str] = Field(None, description="OKPD2 code")
    customer_region: str = Field("СЗФО", description="Customer region")
    law: str = Field("44-ФЗ", description="Procurement law")
    date_from: date = Field(..., description="Start date for search")
    date_to: date = Field(..., description="End date for search")
    execution_statuses: List[str] = Field(
        ["Исполнение завершено", "Исполнение прекращено"], 
        description="Execution statuses"
    )
    limit_contracts: int = Field(30, ge=1, le=1000, description="Maximum number of contracts to process")
    input_source: InputSource = Field(InputSource.MANUAL, description="Source of input data")
    
    @validator('date_to')
    def validate_dates(cls, v, values):
        if 'date_from' in values and v < values['date_from']:
            raise ValueError('date_to must be after date_from')
        return v


class SearchResponse(BaseModel):
    """Search response model."""
    id: UUID
    status: SearchStatus
    created_at: datetime
    object_name: str
    ktru_code: str
    okpd2_code: Optional[str]
    customer_region: str
    law: str
    date_from: datetime
    date_to: datetime
    execution_statuses: List[str]
    limit_contracts: int
    input_source: InputSource
    found_total: Optional[int] = None
    processed_count: int = 0
    nmc_value: Optional[float] = None
    selected_contract_ids: List[str] = []
    runtime_ms: Optional[int] = None
    error_message: Optional[str] = None


class ContractResultResponse(BaseModel):
    """Contract result response model."""
    id: UUID
    search_id: UUID
    reestr_number: str
    contract_url: str
    sign_date: datetime
    unit_price: Optional[float]
    currency: str
    match_type: str
    ai_score: int
    manufacturer_target: Optional[str]
    manufacturer_found: Optional[str]
    manufacturer_match: Optional[bool]
    is_2025_plus: bool
    accepted_for_nmc: bool
    raw_data_json: Dict[str, Any]
    created_at: datetime


class SearchResultsResponse(BaseModel):
    """Search results response model."""
    search_id: UUID
    results: List[ContractResultResponse]
    total: int
    page: int
    limit: int


class SearchHistoryResponse(BaseModel):
    """Search history response model."""
    searches: List[SearchResponse]
    total: int
    page: int
    limit: int


class StopSearchResponse(BaseModel):
    """Stop search response model."""
    message: str
    search_id: UUID
    status: SearchStatus


# Background task function (placeholder for actual implementation)
def process_search_background(search_id: str, db: Session):
    """
    Background task to process search request.
    
    Args:
        search_id: ID of the search request
        db: Database session
    """
    # This would contain the actual search logic
    # For now, we'll just update the status to DONE after a delay
    import time
    time.sleep(2)  # Simulate processing
    
    # Update search status
    search = db.query(SearchRequestModel).filter(SearchRequestModel.id == search_id).first()
    if search:
        search.status = SearchStatus.DONE
        search.found_total = 10  # Example value
        search.processed_count = 5  # Example value
        search.nmc_value = 150000.0  # Example value
        search.runtime_ms = 2000  # Example value
        db.commit()


@router.post("/", response_model=SearchResponse)
async def create_search(
    request: SearchRequestCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new search for contracts.
    
    This endpoint initiates a search for contracts based on the provided criteria.
    The search runs in the background.
    """
    # Create search request in database
    search_request = SearchRequestModel(
        id=str(uuid4()),
        object_name=request.object_name,
        ktru_code=request.ktru_code,
        okpd2_code=request.okpd2_code,
        customer_region=request.customer_region,
        law=request.law,
        date_from=datetime.combine(request.date_from, datetime.min.time()),
        date_to=datetime.combine(request.date_to, datetime.max.time()),
        execution_statuses=request.execution_statuses,
        limit_contracts=request.limit_contracts,
        input_source=request.input_source,
        status=SearchStatus.RUNNING
    )
    
    db.add(search_request)
    db.commit()
    db.refresh(search_request)
    
    # Add background task
    background_tasks.add_task(process_search_background, search_request.id, db)
    
    # Convert to response model
    return SearchResponse(
        id=UUID(search_request.id),
        status=search_request.status,
        created_at=search_request.created_at,
        object_name=search_request.object_name,
        ktru_code=search_request.ktru_code,
        okpd2_code=search_request.okpd2_code,
        customer_region=search_request.customer_region,
        law=search_request.law,
        date_from=search_request.date_from,
        date_to=search_request.date_to,
        execution_statuses=search_request.execution_statuses,
        limit_contracts=search_request.limit_contracts,
        input_source=search_request.input_source,
        found_total=search_request.found_total,
        processed_count=search_request.processed_count,
        nmc_value=search_request.nmc_value,
        selected_contract_ids=search_request.selected_contract_ids,
        runtime_ms=search_request.runtime_ms,
        error_message=search_request.error_message
    )


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get details of a specific search.
    """
    search_request = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    return SearchResponse(
        id=UUID(search_request.id),
        status=search_request.status,
        created_at=search_request.created_at,
        object_name=search_request.object_name,
        ktru_code=search_request.ktru_code,
        okpd2_code=search_request.okpd2_code,
        customer_region=search_request.customer_region,
        law=search_request.law,
        date_from=search_request.date_from,
        date_to=search_request.date_to,
        execution_statuses=search_request.execution_statuses,
        limit_contracts=search_request.limit_contracts,
        input_source=search_request.input_source,
        found_total=search_request.found_total,
        processed_count=search_request.processed_count,
        nmc_value=search_request.nmc_value,
        selected_contract_ids=search_request.selected_contract_ids,
        runtime_ms=search_request.runtime_ms,
        error_message=search_request.error_message
    )


@router.get("/{search_id}/results", response_model=SearchResultsResponse)
async def get_search_results(
    search_id: UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """
    Get results of a specific search.
    """
    # Check if search exists
    search_request = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Get total count
    total = db.query(ContractResultModel).filter(ContractResultModel.search_id == str(search_id)).count()
    
    # Get paginated results
    results = db.query(ContractResultModel)\
        .filter(ContractResultModel.search_id == str(search_id))\
        .order_by(desc(ContractResultModel.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    # Convert to response models
    result_responses = []
    for result in results:
        result_responses.append(ContractResultResponse(
            id=UUID(result.id),
            search_id=UUID(result.search_id),
            reestr_number=result.reestr_number,
            contract_url=result.contract_url,
            sign_date=result.sign_date,
            unit_price=result.unit_price,
            currency=result.currency,
            match_type=result.match_type.value,
            ai_score=result.ai_score,
            manufacturer_target=result.manufacturer_target,
            manufacturer_found=result.manufacturer_found,
            manufacturer_match=result.manufacturer_match,
            is_2025_plus=result.is_2025_plus,
            accepted_for_nmc=result.accepted_for_nmc,
            raw_data_json=result.raw_data_json,
            created_at=result.created_at
        ))
    
    return SearchResultsResponse(
        search_id=search_id,
        results=result_responses,
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        limit=limit
    )


@router.post("/{search_id}/stop", response_model=StopSearchResponse)
async def stop_search(
    search_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Stop a running search.
    """
    search_request = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Only stop if currently running
    if search_request.status == SearchStatus.RUNNING:
        search_request.status = SearchStatus.STOPPED
        db.commit()
        
        # TODO: Actually signal the background worker to stop
        # This would involve Celery task revocation or similar mechanism
    
    return StopSearchResponse(
        message=f"Search {search_id} stopped successfully",
        search_id=search_id,
        status=search_request.status
    )


@router.get("/history", response_model=SearchHistoryResponse)
async def get_search_history(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[SearchStatus] = Query(None, description="Filter by status"),
    date_from: Optional[date] = Query(None, description="Filter by creation date from"),
    date_to: Optional[date] = Query(None, description="Filter by creation date to"),
    db: Session = Depends(get_db)
):
    """
    Get search history with filters.
    """
    # Build query
    query = db.query(SearchRequestModel)
    
    # Apply filters
    if status:
        query = query.filter(SearchRequestModel.status == status)
    
    if date_from:
        query = query.filter(SearchRequestModel.created_at >= datetime.combine(date_from, datetime.min.time()))
    
    if date_to:
        query = query.filter(SearchRequestModel.created_at <= datetime.combine(date_to, datetime.max.time()))
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    searches = query.order_by(desc(SearchRequestModel.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    # Convert to response models
    search_responses = []
    for search in searches:
        search_responses.append(SearchResponse(
            id=UUID(search.id),
            status=search.status,
            created_at=search.created_at,
            object_name=search.object_name,
            ktru_code=search.ktru_code,
            okpd2_code=search.okpd2_code,
            customer_region=search.customer_region,
            law=search.law,
            date_from=search.date_from,
            date_to=search.date_to,
            execution_statuses=search.execution_statuses,
            limit_contracts=search.limit_contracts,
            input_source=search.input_source,
            found_total=search.found_total,
            processed_count=search.processed_count,
            nmc_value=search.nmc_value,
            selected_contract_ids=search.selected_contract_ids,
            runtime_ms=search.runtime_ms,
            error_message=search.error_message
        ))
    
    return SearchHistoryResponse(
        searches=search_responses,
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        limit=limit
    )