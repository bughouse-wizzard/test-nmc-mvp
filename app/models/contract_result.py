from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Enum, JSON, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum
import uuid


class MatchType(enum.Enum):
    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"


class ContractResult(Base):
    __tablename__ = "contract_result"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    search_id = Column(String, ForeignKey("search_request.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Contract identification
    reestr_number = Column(String, nullable=False, index=True)
    contract_url = Column(String, nullable=False)
    sign_date = Column(DateTime(timezone=True), nullable=False)
    
    # Price information
    unit_price = Column(Float, nullable=True)
    currency = Column(String, nullable=True, default="RUB")
    
    # Matching results
    match_type = Column(Enum(MatchType), nullable=False)
    ai_score = Column(Integer, nullable=False)  # 0..100
    
    # Manufacturer information
    manufacturer_target = Column(String, nullable=True)
    manufacturer_found = Column(String, nullable=True)
    manufacturer_match = Column(Boolean, nullable=True)
    
    # Contract metadata
    is_2025_plus = Column(Boolean, nullable=False, default=False)
    accepted_for_nmc = Column(Boolean, nullable=False, default=False)
    
    # Raw data
    raw_data_json = Column(JSON, nullable=False)
    
    # Relationships
    search = relationship("SearchRequest", backref="contract_results")
    spec_comparisons = relationship("SpecComparisonRow", backref="contract_result", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ContractResult(id={self.id}, reestr_number={self.reestr_number}, match_type={self.match_type})>"