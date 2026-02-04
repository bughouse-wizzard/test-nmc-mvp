from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SearchRequest as SearchRequestModel, SearchStatus

router = APIRouter()


class SearchEvent(BaseModel):
    """Search event model for SSE."""
    type: str
    data: dict
    timestamp: datetime


async def search_progress_generator(search_id: UUID, db: Session):
    """Generate SSE events for search progress."""
    # Check if search exists
    search = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    if not search:
        yield f"event: error\ndata: {json.dumps({'message': 'Search not found'})}\n\n"
        return
    
    # Send initial status
    yield f"event: status\ndata: {json.dumps({
        'search_id': str(search_id),
        'status': search.status.value,
        'processed_count': search.processed_count,
        'found_total': search.found_total,
        'nmc_value': search.nmc_value
    })}\n\n"
    
    # Simulate progress updates (in real implementation, this would listen to actual progress)
    # For now, we'll simulate updates for demonstration
    if search.status == SearchStatus.RUNNING:
        max_updates = 10
        for i in range(max_updates):
            await asyncio.sleep(1)  # Simulate delay between updates
            
            # In real implementation, we would check actual progress from database
            # For simulation, we'll send incremental progress
            progress_data = {
                'search_id': str(search_id),
                'status': search.status.value,
                'processed_count': min(search.processed_count + (i + 1) * 3, 100),
                'found_total': search.found_total or 0 + (i + 1),
                'message': f'Processing contract {i + 1} of {max_updates}'
            }
            
            yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
        
        # Send completion event
        yield f"event: complete\ndata: {json.dumps({
            'search_id': str(search_id),
            'status': 'COMPLETED',
            'message': 'Search completed successfully'
        })}\n\n"
    else:
        # For non-running searches, just send current status
        yield f"event: status\ndata: {json.dumps({
            'search_id': str(search_id),
            'status': search.status.value,
            'message': f'Search is in {search.status.value} state'
        })}\n\n"


@router.get("/search/{search_id}/events")
async def stream_search_events(search_id: UUID, db: Session = Depends(get_db)):
    """Stream Server-Sent Events for search progress."""
    
    # Verify search exists
    search = db.query(SearchRequestModel).filter(SearchRequestModel.id == str(search_id)).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    return StreamingResponse(
        search_progress_generator(search_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
        }
    )