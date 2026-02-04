from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Enum, JSON, Text
from sqlalchemy.sql import func
from app.db.base import Base
import enum
import uuid


class SearchStatus(enum.Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class InputSource(enum.Enum):
    MANUAL = "MANUAL"
    FILE = "FILE"


class SearchRequest(Base):
    __tablename__ = "search_request"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum(SearchStatus), nullable=False, default=SearchStatus.RUNNING)
    input_source = Column(Enum(InputSource), nullable=False)
    
    # Search parameters
    object_name = Column(String, nullable=True)
    ktru_code = Column(String, nullable=False)
    okpd2_code = Column(String, nullable=True)
    customer_region = Column(String, nullable=False, default="СЗФО")  # MVP: СЗФО
    law = Column(String, nullable=False, default="44")  # 44-ФЗ
    date_from = Column(DateTime(timezone=True), nullable=False)
    date_to = Column(DateTime(timezone=True), nullable=False)
    execution_statuses = Column(JSON, nullable=False, default=["Исполнение завершено", "Исполнение прекращено"])
    limit_contracts = Column(Integer, nullable=False, default=30)
    
    # Results
    found_total = Column(Integer, nullable=True)
    processed_count = Column(Integer, nullable=False, default=0)
    nmc_value = Column(Float, nullable=True)
    selected_contract_ids = Column(JSON, nullable=True, default=[])  # IDs of selected contracts for NMC calculation
    
    # Performance and errors
    runtime_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<SearchRequest(id={self.id}, status={self.status}, ktru_code={self.ktru_code})>"