"""
AI service module for DeepSeek integration.
Provides LLM-based text processing and analysis capabilities.
"""

from .client import DeepSeekClient
from .prompts import (
    extract_specs_from_tz,
    extract_specs_from_contract_doc,
    compare_specs_and_score,
)

__all__ = [
    "DeepSeekClient",
    "extract_specs_from_tz",
    "extract_specs_from_contract_doc",
    "compare_specs_and_score",
]