from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import os
from enum import Enum

app = FastAPI(
    title="НМЦК Расчет API",
    description="API для расчета начальной максимальной цены контракта на основе анализа госзакупок",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class SearchStatus(str, Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class InputSource(str, Enum):
    MANUAL = "MANUAL"
    FILE = "FILE"

class MatchType(str, Enum):
    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"

class SearchRequestCreate(BaseModel):
    object_name: str = Field(..., description="Наименование объекта закупки")
    ktru_code: str = Field(..., description="Код КТРУ")
    okpd2_code: Optional[str] = Field(None, description="Код ОКПД2")
    customer_region: str = Field("СЗФО", description="Регион заказчика")
    date_from: datetime = Field(..., description="Дата начала периода")
    date_to: datetime = Field(..., description="Дата окончания периода")
    limit_contracts: int = Field(30, description="Лимит контрактов для обработки")
    execution_statuses: List[str] = Field(["Исполнение завершено", "Исполнение прекращено"], description="Статусы исполнения")
    law: str = Field("44-ФЗ", description="Закон о контрактной системе")

class SearchRequestResponse(BaseModel):
    id: str
    created_at: datetime
    status: SearchStatus
    input_source: InputSource
    object_name: str
    ktru_code: str
    okpd2_code: Optional[str]
    customer_region: str
    law: str
    date_from: datetime
    date_to: datetime
    limit_contracts: int
    execution_statuses: List[str]
    found_total: Optional[int]
    processed_count: int
    nmc_value: Optional[float]
    runtime_ms: Optional[int]
    error_message: Optional[str]

class ContractResult(BaseModel):
    id: str
    search_id: str
    reestr_number: str
    contract_url: str
    sign_date: datetime
    unit_price: Optional[float]
    currency: str = "RUB"
    match_type: MatchType
    ai_score: int = Field(..., ge=0, le=100)
    manufacturer_target: Optional[str]
    manufacturer_found: Optional[str]
    manufacturer_match: Optional[bool]
    is_2025_plus: bool = False
    accepted_for_nmc: bool = False
    created_at: datetime

class SpecComparisonRow(BaseModel):
    contract_result_id: str
    name: str
    target_value: str
    actual_value: str
    match_status: str = Field(..., description="MATCH|DIFF|UNKNOWN")
    weight: int = 1

# In-memory storage (for MVP)
search_requests_db = {}
contract_results_db = {}
spec_comparisons_db = {}

@app.get("/")
async def root():
    return {
        "message": "НМЦК Расчет API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running",
            "database": "connected"  # In real implementation, check DB connection
        }
    }

@app.post("/api/search", response_model=SearchRequestResponse)
async def create_search(request: SearchRequestCreate, background_tasks: BackgroundTasks):
    """Создать новый поиск контрактов"""
    search_id = str(uuid.uuid4())
    now = datetime.now()
    
    search_request = {
        "id": search_id,
        "created_at": now,
        "status": SearchStatus.RUNNING,
        "input_source": InputSource.MANUAL,
        **request.dict(),
        "found_total": None,
        "processed_count": 0,
        "nmc_value": None,
        "runtime_ms": None,
        "error_message": None
    }
    
    search_requests_db[search_id] = search_request
    
    # In real implementation, this would start a background task
    # background_tasks.add_task(process_search, search_id)
    
    return search_request

@app.get("/api/search", response_model=List[SearchRequestResponse])
async def list_searches(
    skip: int = 0,
    limit: int = 100,
    status: Optional[SearchStatus] = None
):
    """Получить список поисков с пагинацией и фильтрацией"""
    searches = list(search_requests_db.values())
    
    if status:
        searches = [s for s in searches if s["status"] == status]
    
    return searches[skip:skip + limit]

@app.get("/api/search/{search_id}", response_model=SearchRequestResponse)
async def get_search(search_id: str):
    """Получить детали поиска по ID"""
    if search_id not in search_requests_db:
        raise HTTPException(status_code=404, detail="Search not found")
    
    return search_requests_db[search_id]

@app.post("/api/search/{search_id}/stop")
async def stop_search(search_id: str):
    """Остановить выполнение поиска"""
    if search_id not in search_requests_db:
        raise HTTPException(status_code=404, detail="Search not found")
    
    search_requests_db[search_id]["status"] = SearchStatus.STOPPED
    
    return {"message": "Search stopped successfully", "search_id": search_id}

@app.get("/api/search/{search_id}/results", response_model=List[ContractResult])
async def get_search_results(
    search_id: str,
    skip: int = 0,
    limit: int = 100,
    min_score: Optional[int] = None
):
    """Получить результаты поиска контрактов"""
    if search_id not in search_requests_db:
        raise HTTPException(status_code=404, detail="Search not found")
    
    results = [
        result for result in contract_results_db.values()
        if result["search_id"] == search_id
    ]
    
    if min_score is not None:
        results = [r for r in results if r["ai_score"] >= min_score]
    
    return results[skip:skip + limit]

@app.get("/api/search/{search_id}/events")
async def get_search_events(search_id: str):
    """SSE endpoint для получения событий о прогрессе поиска"""
    # This would be implemented with Server-Sent Events
    # For MVP, returning a simple response
    if search_id not in search_requests_db:
        raise HTTPException(status_code=404, detail="Search not found")
    
    return {
        "search_id": search_id,
        "events_available": True,
        "endpoint": f"/api/search/{search_id}/events/sse"  # Real SSE endpoint
    }

@app.get("/api/search/{search_id}/report")
async def download_report(search_id: str):
    """Скачать отчет по поиску"""
    if search_id not in search_requests_db:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # In real implementation, generate and return report file
    return {
        "search_id": search_id,
        "report_available": True,
        "formats": ["json", "xlsx", "csv"],
        "download_url": f"/api/search/{search_id}/report/file"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)