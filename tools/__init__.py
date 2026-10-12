"""
GCPL Financial Intelligence Agent - Specialized Tools Package
Phase 2: 5 ftm tools + qtd/ytd + budget + growth + fy/half + margins (10 tools).
"""

from .annual import query_fy_half
from .basic_metrics import query_basic_metrics
from .budget_actual import query_budget_variance
from .cumulative import query_qtd_ytd
from .driver_analysis import analyze_drivers
from .growth import query_yoy_growth
from .margins import query_margin
from .rankings_extrema import find_rankings_extrema
from .region_comparison import compare_regions
from .time_series import analyze_time_series

__all__ = [
    "query_basic_metrics",
    "analyze_time_series",
    "find_rankings_extrema",
    "compare_regions",
    "analyze_drivers",
    "query_qtd_ytd",
    "query_budget_variance",
    "query_yoy_growth",
    "query_fy_half",
    "query_margin",
]
