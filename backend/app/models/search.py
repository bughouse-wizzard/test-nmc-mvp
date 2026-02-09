"""
SearchRequest model for NMCK calculation system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import UUID, String, DateTime, Enum as SQLEnum, Integer, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class SearchStatus(str, Enum):
    """Status of a search request"""
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class InputSource(str, Enum):
    """Source of input data"""
    MANUAL = "MANUAL"
    FILE = "FILE"


class SearchRequest(Base):
    """
    Search request model representing a user's search for contracts.
    
    Attributes:
        id: UUID primary key
        status: Current status of the search (RUNNING, DONE, STOPPED, ERROR)
        input_source: Source of input data
        ktru_code: KTRU code (unified commodity position)
        object_name: Name of the procurement object
        limit_contracts: Maximum number of contracts to process (default 30)
        nmc_value: Calculated NMCK value
        selected_contract_ids: List of contract IDs selected for NMCK calculation
        created_at: Timestamp when search was created
    """
    __tablename__ = "search_request"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    status: Mapped[SearchStatus] = mapped_column(
        SQLEnum(SearchStatus),
        default=SearchStatus.RUNNING,
        nullable=False
    )
    
    input_source: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )
    
    ktru_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    object_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    limit_contracts: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False
    )
    
    nmc_value: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    selected_contract_ids: Mapped[List[str]] = mapped_column(
        JSON,
        default=list
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    contract_results: Mapped[list["ContractResult"]] = relationship(
        "ContractResult",
        back_populates="search_request",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<SearchRequest(id={self.id}, status={self.status}, object={self.object_name})>"