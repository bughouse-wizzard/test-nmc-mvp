from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

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
    execution_statuses: List[str] = Field(
        ["Исполнение завершено", "Исполнение прекращено"],
        description="Статусы исполнения",
    )
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


@router.post("/", response_model=SearchResponse)
async def create_search(request: SearchRequest, background_tasks: BackgroundTasks):
    """Create a new search."""
    # TODO: Implement actual search creation
    # For now, return a mock response
    from uuid import uuid4

    return SearchResponse(
        id=uuid4(),
        status="RUNNING",
        created_at=datetime.now(),
        object_name=request.object_name,
        ktru_code=request.ktru_code,
        found_total=0,
        processed_count=0,
        nmc_value=None,
    )


@router.get("/", response_model=List[SearchResponse])
async def list_searches(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
):
    """List all searches."""
    # TODO: Implement actual search listing
    # For now, return empty list
    return []


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(search_id: UUID):
    """Get search by ID."""
    # TODO: Implement actual search retrieval
    raise HTTPException(status_code=404, detail="Search not found")


@router.post("/{search_id}/stop")
async def stop_search(search_id: UUID):
    """Stop a running search."""
    # TODO: Implement actual search stopping
    return {"message": f"Search {search_id} stopped successfully"}


@router.get("/{search_id}/results")
async def get_search_results(search_id: UUID, skip: int = 0, limit: int = 100):
    """Get search results."""
    # TODO: Implement actual results retrieval
    return {"results": [], "total": 0}
