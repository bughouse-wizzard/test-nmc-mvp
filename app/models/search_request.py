"""SearchRequest model."""
from sqlalchemy import Column, String, Integer, Enum, JSON, Boolean, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
import json

from .base import BaseModel

class SearchStatus(enum.Enum):
    """Search request status."""
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class InputSource(enum.Enum):
    """Input source for search."""
    MANUAL = "MANUAL"
    FILE = "FILE"

class SearchRequest(BaseModel):
    """Search request model."""
    __tablename__ = "search_request"
    
    # Status and basic info
    status = Column(Enum(SearchStatus), nullable=False, default=SearchStatus.RUNNING)
    input_source = Column(Enum(InputSource), nullable=False)
    
    # Search parameters
    object_name = Column(String, nullable=False)
    ktru_code = Column(String, nullable=False)
    okpd2_code = Column(String, nullable=True)
    customer_region = Column(String, nullable=False, default="СЗФО")  # MVP: СЗФО
    law = Column(String, nullable=False, default="44")  # 44-ФЗ
    date_from = Column(String, nullable=False)  # Format: YYYY-MM-DD
    date_to = Column(String, nullable=False)    # Format: YYYY-MM-DD
    
    # Execution statuses (JSON string for SQLite compatibility)
    execution_statuses = Column(Text, nullable=False, default='["Исполнение завершено", "Исполнение прекращено"]')
    
    # Limits and counters
    limit_contracts = Column(Integer, nullable=False, default=30)
    found_total = Column(Integer, nullable=True)  # Total found on website
    processed_count = Column(Integer, nullable=False, default=0)
    
    # Results
    nmc_value = Column(Float, nullable=True)  # Calculated NMCK value
    runtime_ms = Column(Integer, nullable=True)  # Runtime in milliseconds
    
    # Selected contracts (JSON string for SQLite compatibility)
    selected_contract_ids = Column(Text, nullable=True)
    
    # Error handling
    error_message = Column(String, nullable=True)
    
    # Relationships
    contract_results = relationship("ContractResult", back_populates="search_request", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SearchRequest(id={self.id}, object_name='{self.object_name}', status={self.status})>"
    
    def get_execution_statuses(self):
        """Get execution statuses as list."""
        if self.execution_statuses:
            return json.loads(self.execution_statuses)
        return []
    
    def set_execution_statuses(self, statuses):
        """Set execution statuses from list."""
        self.execution_statuses = json.dumps(statuses)
    
    def get_selected_contract_ids(self):
        """Get selected contract IDs as list."""
        if self.selected_contract_ids:
            return json.loads(self.selected_contract_ids)
        return []
    
    def set_selected_contract_ids(self, ids):
        """Set selected contract IDs from list."""
        self.selected_contract_ids = json.dumps([str(id) for id in ids])