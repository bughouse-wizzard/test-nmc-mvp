"""
Search endpoints for contract search and NMCK calculation.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
import asyncio
import json
from pydantic import BaseModel, Field
from datetime import datetime

from ...core.event_channel import event_channel
from ...core.events import event_to_sse_format
from ...worker.tasks import process_search

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
    The search runs in the background using Celery.
    """
    from uuid import uuid4
    from datetime import datetime
    
    # Generate search ID
    search_id = uuid4()
    
    # Initialize event channel
    await event_channel.initialize()
    
    # Start background task
    try:
        process_search.delay(str(search_id))
    except Exception as e:
        # If Celery fails, we can still return the search ID
        # The frontend will connect to SSE but won't get updates
        print(f"Warning: Failed to start Celery task: {e}")
        # Send an immediate error event
        from ...core.events import ErrorEvent
        error_event = ErrorEvent(
            search_id=str(search_id),
            error_message=f"Failed to start background worker: {str(e)}",
            error_type="worker_error"
        )
        await event_channel.publish(str(search_id), error_event)
    
    # TODO: Save search request to database
    # For now, return response with search ID
    
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
                # Parse the event data to extract event type
                try:
                    event_dict = json.loads(event_data)
                    event_type = event_dict.get("type", "message")
                except json.JSONDecodeError:
                    # If we can't parse JSON, use default type
                    event_type = "message"
                
                # Format as SSE
                yield f"event: {event_type}\n"
                yield f"data: {event_data}\n\n"
                
                # Keep connection alive
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
        }
    )