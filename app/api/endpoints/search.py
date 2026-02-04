from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json

from app.db.session import get_db
from app.models import SearchRequest as SearchRequestModel, ContractResult, SearchStatus, InputSource

router = APIRouter()


class SearchRequest(BaseModel):
    """Search request model."""
    object_name: str = Field(..., description="Наименование объекта закупки")
    ktru_code: str = Field(..., description="Код КТРУ")
    okpd2_code: Optional[str] = Field(None, description="Код ОКПД2")
    customer_region: str = Field("СЗФО", description="Регион/округ заказчика")
    law: str = Field("44", description="Закон (44-ФЗ)")
    date_from: datetime = Field(..., description="Дата начала периода")
    date_to: datetime = Field(..., description="Дата окончания периода")
    execution_statuses: List[str] = Field(["Исполнение завершено", "Исполнение прекращено"], description="Статусы исполнения")
    limit_contracts: int = Field(30, description="Лимит обработки контрактов")
    input_source: str = Field("MANUAL", description="Источник ввода (MANUAL|FILE)")


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


class SearchResultItem(BaseModel):
    """Search result item model."""
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


class SearchResultsResponse(BaseModel):
    """Search results response model."""
    results: List[SearchResultItem]
    total: int
    skip: int
    limit: int


@router.post("/", response_model=SearchResponse)
async def create_search(
    request: SearchRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new search."""
    # Create search request in database
    db_search = SearchRequestModel(
        object_name=request.object_name,
        ktru_code=request.ktru_code,
        okpd2_code=request.okpd2_code,
        customer_region=request.customer_region,
        law=request.law,
        date_from=request.date_from.strftime("%Y-%m-%d"),
        date_to=request.date_to.strftime("%Y-%m-%d"),
        limit_contracts=request.limit_contracts,
        input_source=InputSource(request.input_source),
        status=SearchStatus.RUNNING,
        processed_count=0,
    )
    
    # Set execution statuses using the model method
    db_search.set_execution_statuses(request.execution_statuses)
    
    db.add(db_search)
    db.commit()
    db.refresh(db_search)
    
    # TODO: Start background task for actual search processing
    # background_tasks.add_task(process_search, db_search.id)
    
    return SearchResponse(
        id=UUID(db_search.id),
        status=db_search.status.value,
        created_at=db_search.created_at,
        object_name=db_search.object_name,
        ktru_code=db_search.ktru_code,
        found_total=db_search.found_total,
        processed_count=db_search.processed_count,
        nmc_value=db_search.nmc_value,
    )


@router.get("/", response_model=List[SearchResponse])
async def list_searches(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all searches."""
    query = db.query(SearchRequestModel)
    
    if status:
        # Convert string status to SearchStatus enum
        try:
            status_enum = SearchStatus(status)
            query = query.filter(SearchRequestModel.status == status_enum)
        except ValueError:
            # If invalid status provided, return empty list
            return []
    
    searches = query.order_by(desc(SearchRequestModel.created_at)).offset(skip).limit(limit).all()
    
    return [
        SearchResponse(
            id=UUID(search.id),
            status=search.status.value,
            created_at=search.created_at,
            object_name=search.object_name,
            ktru_code=search.ktru_code,
            found_total=search.found_total,
            processed_count=search.processed_count,
            nmc_value=search.nmc_value,
        )
        for search in searches
    ]


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(search_id: UUID, db: Session = Depends(get_db)):
    """Get search by ID."""
    search = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    return SearchResponse(
        id=UUID(search.id),
        status=search.status.value,
        created_at=search.created_at,
        object_name=search.object_name,
        ktru_code=search.ktru_code,
        found_total=search.found_total,
        processed_count=search.processed_count,
        nmc_value=search.nmc_value,
    )


@router.post("/{search_id}/stop")
async def stop_search(search_id: UUID, db: Session = Depends(get_db)):
    """Stop a running search."""
    search = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    if search.status not in [SearchStatus.RUNNING, SearchStatus.PAUSED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot stop search with status: {search.status.value}"
        )
    
    search.status = SearchStatus.STOPPED
    db.commit()
    
    return {"message": f"Search {search_id} stopped successfully"}


@router.get("/{search_id}/results", response_model=SearchResultsResponse)
async def get_search_results(
    search_id: UUID, 
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get search results."""
    # Check if search exists
    search = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Get contract results for this search
    query = db.query(ContractResult).filter(ContractResult.search_id == str(search_id))
    total = query.count()
    
    contract_results = query.order_by(ContractResult.created_at.desc()).offset(skip).limit(limit).all()
    
    results = [
        SearchResultItem(
            id=UUID(result.id),
            search_id=UUID(result.search_id),
            reestr_number=result.reestr_number,
            contract_url=result.contract_url,
            sign_date=datetime.fromisoformat(result.sign_date) if result.sign_date else datetime.now(),
            unit_price=result.unit_price,
            currency=result.currency,
            match_type=result.match_type.value if result.match_type else "NO_MATCH",
            ai_score=result.ai_score,
            manufacturer_target=result.manufacturer_target,
            manufacturer_found=result.manufacturer_found,
            manufacturer_match=result.manufacturer_match,
            is_2025_plus=result.is_2025_plus,
            accepted_for_nmc=result.accepted_for_nmc,
            created_at=result.created_at,
        )
        for result in contract_results
    ]
    
    return SearchResultsResponse(
        results=results,
        total=total,
        skip=skip,
        limit=limit,
    )