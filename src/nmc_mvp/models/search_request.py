from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func

from .base import BaseModel
from .enums import SearchStatus, InputSource


class SearchRequest(BaseModel):
    __tablename__ = "search_request"
    
    # Status and source
    status = Column(SQLEnum(SearchStatus), nullable=False, default=SearchStatus.RUNNING)
    input_source = Column(SQLEnum(InputSource), nullable=False)
    
    # Search parameters
    object_name = Column(String, nullable=False)
    ktru_code = Column(String, nullable=False)
    okpd2_code = Column(String, nullable=True)
    customer_region = Column(String, nullable=False, default="СЗФО")  # MVP: СЗФО
    law = Column(String, nullable=False, default="44")  # 44-ФЗ
    
    # Date range
    date_from = Column(DateTime(timezone=True), nullable=False)
    date_to = Column(DateTime(timezone=True), nullable=False)
    
    # Execution statuses (array of strings)
    execution_statuses = Column(ARRAY(String), nullable=False, default=["Исполнение завершено", "Исполнение прекращено"])
    
    # Limits and counters
    limit_contracts = Column(Integer, nullable=False, default=30)
    found_total = Column(Integer, nullable=True)  # Number found on website
    processed_count = Column(Integer, nullable=False, default=0)
    
    # Results
    nmc_value = Column(Float, nullable=True)  # Calculated NMC value
    selected_contract_ids = Column(ARRAY(String), nullable=True)  # IDs of selected contracts for NMC calculation
    
    # Performance and errors
    runtime_ms = Column(Integer, nullable=True)  # Runtime in milliseconds
    error_message = Column(String, nullable=True)
    
    # Additional metadata
    user_id = Column(String, nullable=True)  # For future authorization
    search_parameters_json = Column(JSON, nullable=True)  # Raw search parameters as JSON
    
    def __repr__(self):
        return f"<SearchRequest(id={self.id}, object_name={self.object_name}, status={self.status})>"