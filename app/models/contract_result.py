"""ContractResult model."""

import enum

from sqlalchemy import (JSON, Boolean, Column, Enum, Float, ForeignKey,
                        Integer, String)
from sqlalchemy.orm import relationship

from .base import BaseModel


class MatchType(enum.Enum):
    """Match type for contract comparison."""

    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"


class ContractResult(BaseModel):
    """Contract result model."""

    __tablename__ = "contract_result"

    # Foreign key to search request
    search_id = Column(
        String,
        ForeignKey("search_request.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Contract identification
    reestr_number = Column(String, nullable=False, index=True)
    contract_url = Column(String, nullable=False)
    sign_date = Column(String, nullable=False)  # Format: YYYY-MM-DD

    # Price information
    unit_price = Column(Float, nullable=True)  # Price per unit
    currency = Column(String, nullable=False, default="RUB")

    # Match analysis
    match_type = Column(Enum(MatchType), nullable=False)
    ai_score = Column(Integer, nullable=False)  # 0-100

    # Manufacturer information
    manufacturer_target = Column(String, nullable=True)
    manufacturer_found = Column(String, nullable=True)
    manufacturer_match = Column(Boolean, nullable=True)

    # Contract metadata
    is_2025_plus = Column(Boolean, nullable=False, default=False)
    accepted_for_nmc = Column(Boolean, nullable=False, default=False)

    # Raw data
    raw_data_json = Column(JSON, nullable=True)  # All parsed data

    # Relationships
    search_request = relationship("SearchRequest", back_populates="contract_results")
    spec_comparisons = relationship(
        "SpecComparisonRow",
        back_populates="contract_result",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ContractResult(id={self.id}, reestr_number='{self.reestr_number}', match_type={self.match_type})>"
