"""
Database models for the NMCK calculation system.
Based on Section 6 specifications from requirements.md
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column, String, DateTime, Enum as SQLEnum, 
    Integer, Float, Boolean, ForeignKey, JSON, Text
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class SearchStatus(str, Enum):
    """Status of a search request"""
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class InputSource(str, Enum):
    """Source of input data for search"""
    MANUAL = "MANUAL"
    FILE = "FILE"


class MatchType(str, Enum):
    """Type of match between target and contract specifications"""
    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"


class MatchStatus(str, Enum):
    """Status of individual specification comparison"""
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


class SearchRequest(Base):
    """
    Search request model representing a user's search for contracts.
    
    Attributes:
        id: UUID primary key
        created_at: Timestamp when search was created
        status: Current status of the search (RUNNING, DONE, STOPPED, ERROR)
        input_source: Source of input data (MANUAL or FILE)
        object_name: Name of the procurement object
        ktru_code: KTRU code (unified commodity position)
        okpd2_code: OKPD2 code (optional)
        customer_region: Customer region (MVP: СЗФО)
        law: Procurement law (44-ФЗ)
        date_from: Start date for contract search
        date_to: End date for contract search
        execution_statuses: List of execution statuses to filter by
        limit_contracts: Maximum number of contracts to process (default 30)
        found_total: Total number of contracts found on the website
        processed_count: Number of contracts actually processed
        nmc_value: Calculated NMCK value
        selected_contract_ids: List of contract IDs selected for NMCK calculation
        runtime_ms: Search execution time in milliseconds
        error_message: Error message if search failed
    """
    __tablename__ = "search_request"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    status: Mapped[SearchStatus] = mapped_column(
        SQLEnum(SearchStatus), 
        default=SearchStatus.RUNNING, 
        nullable=False
    )
    input_source: Mapped[InputSource] = mapped_column(
        SQLEnum(InputSource), 
        nullable=False
    )
    
    # Input parameters
    object_name: Mapped[str] = mapped_column(String(500), nullable=False)
    ktru_code: Mapped[str] = mapped_column(String(100), nullable=False)
    okpd2_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_region: Mapped[str] = mapped_column(String(200), nullable=False)
    law: Mapped[str] = mapped_column(String(50), default="44-ФЗ", nullable=False)
    date_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    date_to: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    execution_statuses: Mapped[List[str]] = mapped_column(
        JSON, 
        default=lambda: ["Исполнение завершено", "Исполнение прекращено"]
    )
    limit_contracts: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    
    # Calculated results
    found_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nmc_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selected_contract_ids: Mapped[List[str]] = mapped_column(
        JSON, 
        default=list
    )
    
    # Performance and error tracking
    runtime_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    contract_results: Mapped[List["ContractResult"]] = relationship(
        "ContractResult", 
        back_populates="search_request",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<SearchRequest(id={self.id}, status={self.status}, object={self.object_name})>"


class ContractResult(Base):
    """
    Contract result model representing a found contract and its analysis.
    
    Attributes:
        id: UUID primary key
        search_id: Foreign key to SearchRequest
        reestr_number: Registry number of the contract
        contract_url: URL to the contract card on zakupki.gov.ru
        sign_date: Date when contract was signed
        unit_price: Price per unit (nullable)
        currency: Currency of the price
        match_type: Type of match (IDENTICAL, HOMOGENEOUS, NO_MATCH)
        ai_score: AI scoring from 0 to 100
        manufacturer_target: Target manufacturer from requirements
        manufacturer_found: Manufacturer found in contract
        manufacturer_match: Whether manufacturers match
        is_2025_plus: Whether contract is from 2025 or later
        accepted_for_nmc: Whether contract is accepted for NMCK calculation
        raw_data_json: Raw parsed data from contract
        created_at: Timestamp when record was created
    """
    __tablename__ = "contract_result"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    search_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("search_request.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Contract identification
    reestr_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    contract_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sign_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Price information
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    
    # Analysis results
    match_type: Mapped[MatchType] = mapped_column(
        SQLEnum(MatchType), 
        nullable=False
    )
    ai_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    manufacturer_target: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    manufacturer_found: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    manufacturer_match: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    is_2025_plus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted_for_nmc: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Raw data
    raw_data_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    # Relationships
    search_request: Mapped["SearchRequest"] = relationship(
        "SearchRequest", 
        back_populates="contract_results"
    )
    spec_comparison_rows: Mapped[List["SpecComparisonRow"]] = relationship(
        "SpecComparisonRow", 
        back_populates="contract_result",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<ContractResult(id={self.id}, reestr={self.reestr_number}, match={self.match_type})>"


class SpecComparisonRow(Base):
    """
    Specification comparison row model representing individual characteristic comparison.
    
    Attributes:
        contract_result_id: Foreign key to ContractResult
        name: Name of the characteristic
        target_value: Target value from requirements
        actual_value: Actual value from contract
        match_status: Match status (MATCH, DIFF, UNKNOWN)
        weight: Importance weight of this characteristic
    """
    __tablename__ = "spec_comparison_row"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    contract_result_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("contract_result.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Comparison data
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    match_status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus), 
        nullable=False
    )
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Relationships
    contract_result: Mapped["ContractResult"] = relationship(
        "ContractResult", 
        back_populates="spec_comparison_rows"
    )
    
    def __repr__(self) -> str:
        return f"<SpecComparisonRow(id={self.id}, name={self.name}, status={self.match_status})>"