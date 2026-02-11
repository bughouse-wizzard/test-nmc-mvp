"""
Server-Sent Events (SSE) stream endpoint for search progress updates.
"""
import asyncio
import json
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import SearchRequest, SearchStatus

router = APIRouter()


@router.get("/{search_id}/events")
async def stream_search_events(
    search_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Stream Server-Sent Events (SSE) for search progress updates.
    
    This endpoint provides real-time updates about search progress by
    periodically polling the database for changes in processed_count
    and found_total fields.
    
    The stream follows the SSE format:
    data: {"processed": 5, "total": 30}\n\n
    
    Args:
        search_id: UUID of the search request
        db: Database session dependency
        
    Returns:
        StreamingResponse with SSE events
    """
    # Check if search exists
    search_request = db.query(SearchRequest).filter(SearchRequest.id == str(search_id)).first()
    
    if not search_request:
        raise HTTPException(status_code=404, detail="Search not found")
    
    async def event_generator():
        """
        Generator function that yields SSE-formatted progress events.
        
        Polls the database every second for progress updates and sends
        events when progress changes.
        """
        try:
            # Track previous values to detect changes
            last_processed = -1
            last_total = -1
            last_status = None
            
            # Continue streaming while search is running
            while True:
                # Refresh the search request from database
                db.refresh(search_request)
                
                current_processed = search_request.processed_count or 0
                current_total = search_request.found_total or 0
                current_status = search_request.status
                
                # Check if we have new progress or status change
                progress_changed = (
                    current_processed != last_processed or 
                    current_total != last_total
                )
                status_changed = current_status != last_status
                
                if progress_changed or status_changed:
                    # Create progress event
                    progress_event = {
                        "processed": current_processed,
                        "total": current_total,
                        "status": current_status.value if hasattr(current_status, 'value') else str(current_status)
                    }
                    
                    # Format as SSE
                    yield f"data: {json.dumps(progress_event)}\n\n"
                    
                    # Update last values
                    last_processed = current_processed
                    last_total = current_total
                    last_status = current_status
                
                # Check if search is done
                if current_status in [SearchStatus.DONE, SearchStatus.STOPPED, SearchStatus.ERROR]:
                    # Send final event
                    final_event = {
                        "processed": current_processed,
                        "total": current_total,
                        "status": current_status.value if hasattr(current_status, 'value') else str(current_status),
                        "completed": True
                    }
                    yield f"data: {json.dumps(final_event)}\n\n"
                    break
                
                # Wait before next poll
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            # Client disconnected
            print(f"Client disconnected from SSE stream for search {search_id}")
        except Exception as e:
            # Send error as SSE event
            error_event = {
                "error": f"Error in event stream: {str(e)}"
            }
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