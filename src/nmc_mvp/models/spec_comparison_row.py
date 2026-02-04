from sqlalchemy import Column, String, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel
from .enums import MatchStatus


class SpecComparisonRow(BaseModel):
    __tablename__ = "spec_comparison_row"
    
    # Foreign key to contract_result
    contract_result_id = Column(UUID(as_uuid=True), ForeignKey("contract_result.id"), nullable=False, index=True)
    
    # Comparison data
    name = Column(String, nullable=False)  # Characteristic name
    target_value = Column(String, nullable=True)  # Required value from TZ
    actual_value = Column(String, nullable=True)  # Actual value from contract
    
    # Matching results
    match_status = Column(SQLEnum(MatchStatus), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)  # Importance weight
    
    # Additional information
    unit = Column(String, nullable=True)  # Unit of measurement
    notes = Column(String, nullable=True)  # Additional notes
    
    def __repr__(self):
        return f"<SpecComparisonRow(id={self.id}, name={self.name}, match_status={self.match_status})>"