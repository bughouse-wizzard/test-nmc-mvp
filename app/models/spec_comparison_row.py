"""SpecComparisonRow model."""

import enum

from sqlalchemy import Column, Enum, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from .base import BaseModel


class MatchStatus(enum.Enum):
    """Match status for specification comparison."""

    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


class SpecComparisonRow(BaseModel):
    """Specification comparison row model."""

    __tablename__ = "spec_comparison_row"

    # Foreign key to contract result
    contract_result_id = Column(
        String,
        ForeignKey("contract_result.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Comparison data
    name = Column(String, nullable=False)  # Characteristic name
    target_value = Column(String, nullable=True)  # Target value from TZ
    actual_value = Column(String, nullable=True)  # Actual value from contract
    match_status = Column(Enum(MatchStatus), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)  # Importance weight

    # Relationships
    contract_result = relationship("ContractResult", back_populates="spec_comparisons")

    def __repr__(self):
        return f"<SpecComparisonRow(id={self.id}, name='{self.name}', status={self.match_status})>"
