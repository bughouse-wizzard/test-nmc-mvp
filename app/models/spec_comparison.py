import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SpecComparisonRow(Base):
    """Specification comparison row model."""

    __tablename__ = "spec_comparison_row"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_result.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_value: Mapped[str] = mapped_column(Text, nullable=False)
    actual_value: Mapped[str] = mapped_column(Text, nullable=False)
    match_status: Mapped[str] = mapped_column(String(10), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    contract: Mapped["ContractResult"] = relationship(
        "ContractResult", back_populates="spec_comparisons"
    )

    def __repr__(self) -> str:
        return f"<SpecComparisonRow(id={self.id}, name={self.name}, match_status={self.match_status})>"
