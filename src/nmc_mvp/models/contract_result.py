from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import BaseModel
from .enums import MatchType


class ContractResult(BaseModel):
    __tablename__ = "contract_result"
    
    # Foreign key to search_request
    search_id = Column(UUID(as_uuid=True), ForeignKey("search_request.id"), nullable=False, index=True)
    
    # Contract identification
    reestr_number = Column(String, nullable=False, index=True)
    contract_url = Column(String, nullable=False)
    sign_date = Column(DateTime(timezone=True), nullable=False)
    
    # Price information
    unit_price = Column(Float, nullable=True)  # Price per unit
    currency = Column(String, nullable=False, default="RUB")
    
    # Matching results
    match_type = Column(String, nullable=False)  # Using String instead of Enum for flexibility
    ai_score = Column(Integer, nullable=False)  # 0-100
    
    # Manufacturer information
    manufacturer_target = Column(String, nullable=True)
    manufacturer_found = Column(String, nullable=True)
    manufacturer_match = Column(Boolean, nullable=True)
    
    # Contract metadata
    is_2025_plus = Column(Boolean, nullable=False, default=False)
    accepted_for_nmc = Column(Boolean, nullable=False, default=False)
    
    # Raw data
    raw_data_json = Column(JSON, nullable=True)  # Everything parsed from contract
    
    # Additional fields for display
    contract_price = Column(Float, nullable=True)  # Total contract price
    customer_name = Column(String, nullable=True)
    supplier_name = Column(String, nullable=True)
    
    # Relationships
    search = relationship("SearchRequest", backref="contract_results")
    spec_comparisons = relationship("SpecComparisonRow", backref="contract_result", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ContractResult(id={self.id}, reestr_number={self.reestr_number}, match_type={self.match_type})>"