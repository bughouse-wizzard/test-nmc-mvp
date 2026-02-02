from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Float, Boolean, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.db import Base


class ContractResult(Base):
    """Contract result model."""
    __tablename__ = "contract_result"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_request.id"), nullable=False)
    reestr_number: Mapped[str] = mapped_column(String(100), nullable=False)
    contract_url: Mapped[str] = mapped_column(Text, nullable=False)
    sign_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unit_price: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ai_score: Mapped[int] = mapped_column(Integer, nullable=False)
    manufacturer_target: Mapped[Optional[str]] = mapped_column(Text)
    manufacturer_found: Mapped[Optional[str]] = mapped_column(Text)
    manufacturer_match: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_2025_plus: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_for_nmc: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data_json: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    search: Mapped["SearchRequest"] = relationship("SearchRequest", back_populates="contracts")
    spec_comparisons: Mapped[list["SpecComparisonRow"]] = relationship(
        "SpecComparisonRow", back_populates="contract", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<ContractResult(id={self.id}, reestr_number={self.reestr_number}, match_type={self.match_type})>"