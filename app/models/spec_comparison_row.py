from sqlalchemy import Column, String, Integer, Float, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum


class MatchStatus(enum.Enum):
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


class SpecComparisonRow(Base):
    __tablename__ = "spec_comparison_row"

    # Using composite primary key: contract_result_id + name
    contract_result_id = Column(String, ForeignKey("contract_result.id"), primary_key=True, nullable=False)
    name = Column(String, primary_key=True, nullable=False)
    
    # Comparison values
    target_value = Column(String, nullable=True)
    actual_value = Column(String, nullable=True)
    match_status = Column(Enum(MatchStatus), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)  # Importance weight

    def __repr__(self):
        return f"<SpecComparisonRow(contract_result_id={self.contract_result_id}, name={self.name}, status={self.match_status})>"