# Models package initialization
from .base import Base, BaseModel
from .search import SearchRequest
from .search_request import SearchRequest as SearchRequestNew, SearchStatus, InputSource
from .contract import ContractResult
from .contract_result import ContractResult as ContractResultNew, MatchType
from .spec_comparison import SpecComparisonRow
from .spec_comparison_row import SpecComparisonRow as SpecComparisonRowNew, MatchStatus

# Use the newer versions if they exist, otherwise fall back to older ones
try:
    SearchRequest = SearchRequestNew
except:
    pass

try:
    ContractResult = ContractResultNew
except:
    pass

try:
    SpecComparisonRow = SpecComparisonRowNew
except:
    pass

__all__ = [
    "Base",
    "BaseModel",
    "SearchRequest",
    "SearchStatus",
    "InputSource",
    "ContractResult",
    "MatchType",
    "SpecComparisonRow",
    "MatchStatus",
]
