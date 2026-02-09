"""
SpecComparisonRow model for detailed line-item matching in NMCK calculation system.
"""

import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import UUID, String, Text, Enum as SQLEnum, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class MatchStatus(str, Enum):
    """Status of individual specification comparison"""
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


class SpecComparisonRow(Base):
    """
    Specification comparison row model representing individual characteristic comparison.
    
    Attributes:
        id: UUID primary key
        contract_result_id: Foreign key to ContractResult
        name: Name of the characteristic
        target_value: Target value from requirements
        actual_value: Actual value from contract
        match_status: Match status (MATCH, DIFF, UNKNOWN)
        weight: Importance weight of this characteristic
    """
    __tablename__ = "spec_comparison_row"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    contract_result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contract_result.id", ondelete="CASCADE"),
        nullable=False
    )
    
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )
    
    target_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    actual_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    match_status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus),
        nullable=False
    )
    
    weight: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    
    # Relationships
    contract_result: Mapped["ContractResult"] = relationship(
        "ContractResult",
        back_populates="spec_comparison_rows"
    )
    
    def __repr__(self) -> str:
        return f"<SpecComparisonRow(id={self.id}, name={self.name}, status={self.match_status})>"