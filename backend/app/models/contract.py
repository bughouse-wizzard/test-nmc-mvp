"""
ContractResult model for NMCK calculation system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from sqlalchemy import UUID, String, DateTime, Enum as SQLEnum, Integer, Numeric, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class MatchType(str, Enum):
    """Type of match between target and contract specifications"""
    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"


class ContractResult(Base):
    """
    Contract result model representing a found contract and its analysis.
    
    Attributes:
        id: UUID primary key
        search_id: Foreign key to SearchRequest
        reestr_number: Registry number of the contract
        contract_url: URL to the contract card on zakupki.gov.ru
        sign_date: Date when contract was signed
        price: Total contract price
        unit_price: Price per unit
        match_type: Type of match (IDENTICAL, HOMOGENEOUS, NO_MATCH)
        ai_score: AI scoring from 0 to 100
        is_2025_plus: Whether contract is from 2025 or later
        raw_data_json: Raw parsed data from contract in JSONB format
    """
    __tablename__ = "contract_result"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    search_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("search_request.id", ondelete="CASCADE"),
        nullable=False
    )
    
    reestr_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    contract_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    sign_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )
    
    price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    unit_price: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    match_type: Mapped[MatchType] = mapped_column(
        SQLEnum(MatchType),
        nullable=False
    )
    
    ai_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    is_2025_plus: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    raw_data_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False
    )
    
    # Relationships
    search_request: Mapped["SearchRequest"] = relationship(
        "SearchRequest",
        back_populates="contract_results"
    )
    
    spec_comparison_rows: Mapped[list["SpecComparisonRow"]] = relationship(
        "SpecComparisonRow",
        back_populates="contract_result",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<ContractResult(id={self.id}, reestr={self.reestr_number}, match={self.match_type})>"