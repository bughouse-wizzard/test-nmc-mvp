"""
Contract-related endpoints.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

from backend.services.parser.contract import ContractParser, ContractParseResult

router = APIRouter()
logger = logging.getLogger(__name__)


class ContractResult(BaseModel):
    """Contract result model."""
    id: UUID
    search_id: UUID
    reestr_number: str
    contract_url: str
    sign_date: datetime
    unit_price: Optional[float] = None
    currency: str = "RUB"
    match_type: str = Field(..., description="IDENTICAL|HOMOGENEOUS|NO_MATCH")
    ai_score: int = Field(..., ge=0, le=100)
    manufacturer_target: Optional[str] = None
    manufacturer_found: Optional[str] = None
    manufacturer_match: Optional[bool] = None
    is_2025_plus: bool = False
    accepted_for_nmc: bool = False
    created_at: datetime


class SpecComparisonRow(BaseModel):
    """Specification comparison row model."""
    name: str
    target_value: str
    actual_value: str
    match_status: str = Field(..., description="MATCH|DIFF|UNKNOWN")
    weight: int = Field(1, ge=1, le=10)


# Pydantic models for parser results
class ContractAttachmentResponse(BaseModel):
    """Contract attachment response model."""
    name: str
    url: str
    file_type: str
    size_bytes: Optional[int] = None
    description: Optional[str] = None


class ContractSpecificationItemResponse(BaseModel):
    """Contract specification item response model."""
    item_number: str
    name: str
    okpd2_code: Optional[str] = None
    ktru_code: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    currency: str = "RUB"
    additional_info: Optional[str] = None


class ContractCommonInfoResponse(BaseModel):
    """Contract common information response model."""
    reestr_number: str
    contract_url: str
    sign_date: Optional[datetime] = None
    customer_name: Optional[str] = None
    supplier_name: Optional[str] = None
    contract_price: Optional[float] = None
    currency: str = "RUB"
    contract_status: Optional[str] = None
    execution_status: Optional[str] = None
    law_type: Optional[str] = None


class ContractParseResponse(BaseModel):
    """Response model for contract parsing."""
    common_info: ContractCommonInfoResponse
    specifications: List[ContractSpecificationItemResponse] = []
    attachments: List[ContractAttachmentResponse] = []
    printed_form_available: bool = False
    printed_form_type: Optional[str] = None
    printed_form_size_bytes: Optional[int] = None
    errors: List[str] = []
    success: bool = True


@router.get("/{contract_id}", response_model=ContractResult)
async def get_contract(contract_id: UUID):
    """
    Get details of a specific contract.
    """
    # TODO: Implement actual retrieval logic
    raise HTTPException(status_code=404, detail="Contract not found")


@router.get("/{contract_id}/comparison")
async def get_contract_comparison(contract_id: UUID):
    """
    Get detailed comparison for a specific contract.
    """
    # TODO: Implement actual comparison retrieval
    return {
        "contract_id": contract_id,
        "comparison_rows": [],
        "summary": {
            "total_rows": 0,
            "matched_rows": 0,
            "different_rows": 0,
            "match_percentage": 0.0
        }
    }


@router.get("/")
async def list_contracts(
    search_id: Optional[UUID] = None,
    match_type: Optional[str] = Query(None, description="Filter by match type"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum AI score"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List contracts with optional filtering.
    """
    # TODO: Implement actual listing logic
    return {
        "contracts": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }


@router.post("/parse", response_model=ContractParseResponse)
async def parse_contract(
    contract_url: str = Query(..., description="URL of the contract to parse")
):
    """
    Parse contract details from zakupki.gov.ru URL.
    
    Features:
    1. Fetch contract common info page (/common-info.html)
    2. Navigate to 'Payments and Objects of Purchase' tab for specifications
    3. Identify and categorize attachments
    4. Download 'Printed Form' for contracts > 2025
    5. Extract unit prices from HTML tables
    """
    try:
        logger.info(f"Parsing contract from URL: {contract_url}")
        
        async with ContractParser() as parser:
            parse_result = await parser.parse_contract(contract_url)
            
            # Convert parser result to response model
            response = _convert_parse_result_to_response(parse_result)
            
            logger.info(f"Successfully parsed contract: {parse_result.common_info.reestr_number}")
            return response
            
    except Exception as e:
        error_msg = f"Failed to parse contract: {str(e)}"
        logger.error(error_msg)
        
        # Return error response
        return ContractParseResponse(
            common_info=ContractCommonInfoResponse(
                reestr_number="ERROR",
                contract_url=contract_url
            ),
            errors=[error_msg],
            success=False
        )


@router.get("/parse/demo")
async def parse_contract_demo():
    """
    Demo endpoint to test contract parsing with a sample URL.
    Returns a mock response showing the structure of parsed data.
    """
    # This is a demo endpoint that returns mock data
    # In production, this would actually parse a real contract
    
    from datetime import datetime
    
    return ContractParseResponse(
        common_info=ContractCommonInfoResponse(
            reestr_number="12345678901234567890",
            contract_url="https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=12345678901234567890",
            sign_date=datetime(2024, 1, 15),
            customer_name='ООО "Тестовый Заказчик"',
            supplier_name='ООО "Тестовый Поставщик"',
            contract_price=1234567.89,
            currency="RUB",
            contract_status="Активный",
            execution_status="Исполнение завершено",
            law_type="44-ФЗ"
        ),
        specifications=[
            ContractSpecificationItemResponse(
                item_number="1",
                name="Тестовый товар 1",
                okpd2_code="12.34.56.789",
                ktru_code="01.02.03",
                unit="шт.",
                quantity=10.0,
                unit_price=1234.56,
                total_price=12345.60,
                currency="RUB"
            ),
            ContractSpecificationItemResponse(
                item_number="2",
                name="Тестовый товар 2",
                okpd2_code="98.76.54.321",
                ktru_code="04.05.06",
                unit="кг",
                quantity=5.5,
                unit_price=500.0,
                total_price=2750.0,
                currency="RUB"
            )
        ],
        attachments=[
            ContractAttachmentResponse(
                name="Договор в формате PDF",
                url="https://zakupki.gov.ru/documents/contract.pdf",
                file_type="pdf",
                description="Основной договор"
            ),
            ContractAttachmentResponse(
                name="Печатная форма",
                url="https://zakupki.gov.ru/documents/printed-form.pdf",
                file_type="pdf",
                description="Printed Form"
            )
        ],
        printed_form_available=True,
        printed_form_type="pdf",
        printed_form_size_bytes=10240,
        errors=[],
        success=True
    )


def _convert_parse_result_to_response(parse_result: ContractParseResult) -> ContractParseResponse:
    """Convert internal parser result to API response model."""
    
    # Convert common info
    common_info_response = ContractCommonInfoResponse(
        reestr_number=parse_result.common_info.reestr_number,
        contract_url=parse_result.common_info.contract_url,
        sign_date=parse_result.common_info.sign_date,
        customer_name=parse_result.common_info.customer_name,
        supplier_name=parse_result.common_info.supplier_name,
        contract_price=parse_result.common_info.contract_price,
        currency=parse_result.common_info.currency,
        contract_status=parse_result.common_info.contract_status,
        execution_status=parse_result.common_info.execution_status,
        law_type=parse_result.common_info.law_type
    )
    
    # Convert specifications
    specifications_response = []
    for spec in parse_result.specifications:
        spec_response = ContractSpecificationItemResponse(
            item_number=spec.item_number,
            name=spec.name,
            okpd2_code=spec.okpd2_code,
            ktru_code=spec.ktru_code,
            unit=spec.unit,
            quantity=spec.quantity,
            unit_price=spec.unit_price,
            total_price=spec.total_price,
            currency=spec.currency,
            additional_info=spec.additional_info
        )
        specifications_response.append(spec_response)
    
    # Convert attachments
    attachments_response = []
    for attachment in parse_result.attachments:
        attachment_response = ContractAttachmentResponse(
            name=attachment.name,
            url=attachment.url,
            file_type=attachment.file_type,
            size_bytes=attachment.size_bytes,
            description=attachment.description
        )
        attachments_response.append(attachment_response)
    
    # Determine printed form info
    printed_form_available = parse_result.printed_form_content is not None
    printed_form_size_bytes = len(parse_result.printed_form_content) if parse_result.printed_form_content else None
    
    return ContractParseResponse(
        common_info=common_info_response,
        specifications=specifications_response,
        attachments=attachments_response,
        printed_form_available=printed_form_available,
        printed_form_type=parse_result.printed_form_type,
        printed_form_size_bytes=printed_form_size_bytes,
        errors=parse_result.errors,
        success=len(parse_result.errors) == 0
    )