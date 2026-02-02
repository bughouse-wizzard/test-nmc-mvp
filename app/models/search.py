import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Float, Integer,
                        String, Text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SearchRequest(Base):
    """Search request model."""

    __tablename__ = "search_request"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    input_source: Mapped[str] = mapped_column(String(10), default="MANUAL")
    object_name: Mapped[str] = mapped_column(Text, nullable=False)
    ktru_code: Mapped[str] = mapped_column(String(50), nullable=False)
    okpd2_code: Mapped[Optional[str]] = mapped_column(String(50))
    customer_region: Mapped[str] = mapped_column(String(100), default="СЗФО")
    law: Mapped[str] = mapped_column(String(10), default="44")
    date_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    execution_statuses: Mapped[List[str]] = mapped_column(
        JSON, default=["Исполнение завершено", "Исполнение прекращено"]
    )
    limit_contracts: Mapped[int] = mapped_column(Integer, default=30)
    found_total: Mapped[Optional[int]] = mapped_column(Integer)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    nmc_value: Mapped[Optional[float]] = mapped_column(Float)
    selected_contract_ids: Mapped[List[str]] = mapped_column(JSON, default=[])
    runtime_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    contracts: Mapped[List["ContractResult"]] = relationship(
        "ContractResult", back_populates="search", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SearchRequest(id={self.id}, object_name={self.object_name}, status={self.status})>"
