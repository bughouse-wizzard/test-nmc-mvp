"""
Search endpoints for contract search and NMCK calculation.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ...core.event_channel import event_channel
from ...core.events import event_to_sse_format
from ...worker.tasks import process_search
from ...database import get_db
from ...models import SearchRequest, ContractResult, SearchStatus, InputSource, MatchType
from services.report import ReportGenerator

router = APIRouter()


# Pydantic schemas
class SearchRequestCreate(BaseModel):
    """Search request creation model."""
    object_name: str = Field(..., description="Name of the procurement object")
    ktru_code: str = Field(..., description="KTRU code")
    okpd2_code: Optional[str] = Field(None, description="OKPD2 code")
    customer_region: str = Field("СЗФО", description="Customer region")
    law: str = Field("44-ФЗ", description="Procurement law")
    date_from: str = Field(..., description="Start date for search (ISO format)")
    date_to: str = Field(..., description="End date for search (ISO format)")
    execution_statuses: List[str] = Field(
        ["Исполнение завершено"], 
        description="Execution statuses"
    )
    limit_contracts: int = Field(30, ge=1, le=1000, description="Maximum number of contracts to process")
    input_source: InputSource = Field(InputSource.MANUAL, description="Source of input data")
    characteristics_text: Optional[str] = Field(None, description="Characteristics text")
    manufacturer: Optional[str] = Field(None, description="Manufacturer")
    
    @validator('date_to')
    def validate_dates(cls, v, values):
        if 'date_from' in values:
            from datetime import datetime
            date_from = datetime.fromisoformat(values['date_from'].replace('Z', '+00:00'))
            date_to = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if date_to < date_from:
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


# Background task function using Celery worker
def process_search_background(search_id: str, db: Session):
    """
    Background task to process search request using Celery worker.
    
    Args:
        search_id: ID of the search request
        db: Database session
    """
    try:
        # Import Celery app and task
        from backend.celery_app import celery_app
        from backend.services.worker.tasks import process_search_task
        
        # Send task to Celery worker
        task_result = process_search_task.delay(search_id)
        
        # Store task ID in search request for future reference
        search = db.query(SearchRequestModel).filter(SearchRequestModel.id == search_id).first()
        if search:
            # Store task ID in raw_data_json or create a new field
            if not search.raw_data_json:
                search.raw_data_json = {}
            search.raw_data_json["celery_task_id"] = task_result.id
            db.commit()
            
    except Exception as e:
        # Log error and update search status
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to start background task for search {search_id}: {e}")
        
        search = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        if search:
            search.status = SearchStatus.ERROR
            search.error_message = f"Failed to start background task: {str(e)}"
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
    The search runs in the background using Celery.
    """
    from uuid import uuid4
    
    # Generate search ID
    search_id = str(uuid4())
    
    # Parse dates from ISO strings
    date_from_dt = datetime.fromisoformat(request.date_from.replace('Z', '+00:00'))
    date_to_dt = datetime.fromisoformat(request.date_to.replace('Z', '+00:00'))
    
    # Create search request in database
    search_request = SearchRequest(
        id=search_id,
        object_name=request.object_name,
        ktru_code=request.ktru_code,
        okpd2_code=request.okpd2_code,
        customer_region=request.customer_region,
        law=request.law,
        date_from=date_from_dt.date(),
        date_to=date_to_dt.date(),
        execution_statuses=request.execution_statuses,
        limit_contracts=request.limit_contracts,
        input_source=request.input_source,
        status=SearchStatus.RUNNING
    )
    
    db.add(search_request)
    db.commit()
    db.refresh(search_request)
    
    # Initialize event channel
    await event_channel.initialize()
    
    # Start background task
    try:
        process_search.delay(search_id)
    except Exception as e:
        # If Celery fails, update status and send error event
        print(f"Warning: Failed to start Celery task: {e}")
        search_request.status = SearchStatus.ERROR
        search_request.error_message = f"Failed to start background worker: {str(e)}"
        db.commit()
        
        # Send an immediate error event
        from ...core.events import ErrorEvent
        error_event = ErrorEvent(
            search_id=search_id,
            error_message=f"Failed to start background worker: {str(e)}",
            error_type="worker_error"
        )
        await event_channel.publish(search_id, error_event)
    
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
    search_request = db.query(SearchRequest).filter(SearchRequest.id == str(search_id)).first()
    
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
    search_request = db.query(SearchRequest).filter(SearchRequest.id == str(search_id)).first()
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Get total count
    total = db.query(ContractResult).filter(ContractResult.search_id == str(search_id)).count()
    
    # Get paginated results
    results = db.query(ContractResult)\
        .filter(ContractResult.search_id == str(search_id))\
        .order_by(desc(ContractResult.created_at))\
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
    search_request = db.query(SearchRequest).filter(SearchRequest.id == str(search_id)).first()
    
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    if search_request.status != SearchStatus.RUNNING:
        raise HTTPException(status_code=400, detail=f"Search is not running. Current status: {search_request.status}")
    
    # Update search status to STOPPED
    search_request.status = SearchStatus.STOPPED
    db.commit()
    
    # Send stop event via SSE
    await event_channel.initialize()
    from ...core.events import DoneEvent
    stop_event = DoneEvent(
        search_id=str(search_id),
        total_found=search_request.found_total or 0,
        total_processed=search_request.processed_count or 0,
        nmc_value=search_request.nmc_value,
        stopped_by_user=True
    )
    await event_channel.publish(str(search_id), stop_event)
    
    return StopSearchResponse(
        message="Search stopped successfully",
        search_id=search_id,
        status=search_request.status
    )


@router.get("/{search_id}/events")
async def stream_search_events(search_id: UUID):
    """
    Stream Server-Sent Events (SSE) for a specific search.
    
    This endpoint provides real-time updates about search progress,
    including:
    - progress: processed count and total found
    - result_added: new contract found and analyzed
    - done: search completed
    - error: error occurred during processing
    
    The stream follows the SSE format:
    event: <event_type>
    data: <json_data>
    
    Example events:
    event: progress
    data: {"type": "progress", "search_id": "...", "processed_count": 5, "found_total": 25, ...}
    
    event: result_added
    data: {"type": "result_added", "search_id": "...", "contract_id": "...", ...}
    """
    # Initialize event channel
    await event_channel.initialize()
    
    async def event_generator():
        """
        Generator function that yields SSE-formatted events.
        """
        try:
            # Subscribe to events for this search
            async for event_data in event_channel.subscribe(search_id):
                # The event_data should already be a JSON string from event_channel
                # Parse it to extract event type for SSE formatting
                try:
                    event_dict = json.loads(event_data)
                    event_type = event_dict.get("type", "message")
                    
                    # Format as SSE
                    yield f"event: {event_type}\n"
                    yield f"data: {event_data}\n\n"
                    
                except json.JSONDecodeError:
                    # If event_data is not valid JSON, send it as a message event
                    yield f"event: message\n"
                    yield f"data: {json.dumps({'message': event_data})}\n\n"
                
                # Keep connection alive with periodic ping
                # This helps prevent connection timeouts
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            # Client disconnected
            print(f"Client disconnected from SSE stream for search {search_id}")
        except Exception as e:
            # Send error as SSE event
            error_event = {
                "type": "error",
                "search_id": str(search_id),
                "error_message": f"Error in event stream: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            yield f"event: error\n"
            yield f"data: {json.dumps(error_event)}\n\n"
    
    # Return streaming response with SSE headers
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
            "Access-Control-Allow-Origin": "*",  # Allow CORS for SSE
        }
    )


@router.get("/{search_id}/report")
async def get_search_report(
    search_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Generate and download XLSX report for a search.
    
    The report contains three sheets:
    1. Summary Sheet: Search parameters and NMCK calculation results
    2. Detailed Sheet: List of all analyzed contracts with match status, price, and manufacturer
    3. Comparison Sheet: Detailed specification comparison for selected contracts
    """
    # Check if search exists
    search_request = db.query(SearchRequest).filter(SearchRequest.id == str(search_id)).first()
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Check if search is completed
    if search_request.status != SearchStatus.DONE:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot generate report for search with status: {search_request.status}. "
                   f"Search must be completed (DONE) to generate report."
        )
    
    try:
        # Generate report
        report_generator = ReportGenerator(db)
        report_bytes = report_generator.generate_search_report(str(search_id))
        
        # Create filename with search ID and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_search_{search_id}_{timestamp}.xlsx"
        
        # Return as streaming response
        return StreamingResponse(
            report_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate report: {str(e)}"
        )


@router.get("/history", response_model=SearchHistoryResponse)
async def get_search_history(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """
    Get search history.
    """
    # Get total count
    total = db.query(SearchRequest).count()
    
    # Get paginated results
    searches = db.query(SearchRequest)\
        .order_by(desc(SearchRequest.created_at))\
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


@router.get("/{search_id}/report")
async def get_search_report(
    search_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Generate and download an XLSX report for a search.
    
    The report includes:
    1. Summary Sheet: Search parameters and NMCK calculation results
    2. Detailed Sheet: List of all analyzed contracts with match status, price, and manufacturer
    3. Comparison Sheet: Detailed spec comparison for selected contracts
    """
    from ...services.report import ReportGenerator
    
    # Check if search exists
    search_request = db.query(SearchRequest).filter(SearchRequest.id == str(search_id)).first()
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Check if search is completed
    if search_request.status != SearchStatus.DONE:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot generate report for search with status: {search_request.status}. Search must be completed."
        )
    
    try:
        # Generate report
        report_generator = ReportGenerator(db)
        report_buffer = report_generator.generate_search_report(str(search_id))
        
        # Create filename
        filename = f"report_search_{search_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Return file as response
        return StreamingResponse(
            report_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")