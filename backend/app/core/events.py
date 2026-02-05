"""
Event models for SSE (Server-Sent Events) streaming.
"""
from enum import Enum
from typing import Optional, Any, Dict
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events that can be sent via SSE."""
    PROGRESS = "progress"
    RESULT_ADDED = "result_added"
    DONE = "done"
    ERROR = "error"


class BaseEvent(BaseModel):
    """Base event model with common fields."""
    type: EventType
    search_id: UUID
    timestamp: datetime = Field(default_factory=datetime.now)


class ProgressEvent(BaseEvent):
    """Progress update event."""
    type: EventType = EventType.PROGRESS
    processed_count: int = Field(..., description="Number of contracts processed so far")
    found_total: int = Field(..., description="Total number of contracts found")
    status: str = Field(..., description="Current status of the search")


class ResultAddedEvent(BaseEvent):
    """Event when a new contract result is added."""
    type: EventType = EventType.RESULT_ADDED
    contract_id: UUID = Field(..., description="ID of the contract result")
    reestr_number: str = Field(..., description="Registry number of the contract")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    match_type: str = Field(..., description="Type of match (IDENTICAL/HOMOGENEOUS)")
    ai_score: int = Field(..., description="AI score from 0-100")
    manufacturer_match: Optional[bool] = Field(None, description="Whether manufacturers match")


class DoneEvent(BaseEvent):
    """Event when search is completed."""
    type: EventType = EventType.DONE
    total_processed: int = Field(..., description="Total number of contracts processed")
    total_found: int = Field(..., description="Total number of contracts found")
    nmc_value: Optional[float] = Field(None, description="Calculated NMCK value")
    selected_count: int = Field(..., description="Number of contracts selected for NMCK calculation")


class ErrorEvent(BaseEvent):
    """Event when an error occurs."""
    type: EventType = EventType.ERROR
    error_message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code if available")


# Union type for all events
Event = ProgressEvent | ResultAddedEvent | DoneEvent | ErrorEvent


def event_to_sse_format(event: Event) -> str:
    """
    Convert an event to SSE format.
    
    SSE format:
    event: <event_type>
    data: <json_data>
    
    Returns:
        Formatted SSE string
    """
    # Get event type from the event object
    event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
    
    # Format as SSE
    lines = [
        f"event: {event_type}",
        f"data: {event.model_dump_json()}",
        ""  # Empty line to separate events
    ]
    
    return "\n".join(lines)