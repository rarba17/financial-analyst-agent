"""
Shared resolvers for GCPL/CCPL financial tools (Phase 0 helper layer).

Centralises region / currency / period / unit handling so every tool
behaves the same way. DB truth is frozen in
`Data Files/distincts.json` (see a.md Phase 0).
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MONTH_ORDER = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
MONTHS_FULL = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
}

# P&L hierarchy used for generic driver decomposition (a.md G17).
# Ordered top-down: each target maps to additive components where possible.
FINANCIAL_HIERARCHY: Dict[str, List[str]] = {
    "ebitda": [
        "gross_contribution_gc_of_gsv",
        "total_a_p_spends",
        "fx_gain_loss",
        "other_income_expenses",
        "inter_co_re_charges_income_expenses",
    ],
    "profit_before_tax": [
        "ebitda",
        "depreciation",
        "net_interest_cost",
        "fx_gain_loss",
        "other_income_expenses",
        "inter_co_re_charges_income_expenses",
        "exceptional_income_expense",
    ],
    "profit_after_tax": [
        "profit_before_tax",
        "taxation",
        "exceptional_income_expense",
    ],
    "net_sales_ind_as": [
        "gross_domestic_sales",
        "gross_export_sales",
        "less_temporary_price_reduction_tpr",
        "less_ind_as_btl_adjustment",
    ],
    "gross_sales": ["gross_domestic_sales", "gross_export_sales"],
    "net_contribution_nc": [
        "gross_contribution_gc_of_gsv",
        "total_a_p_spends",
    ],
    "ebit": ["ebitda", "depreciation"],
}

# Cluster view order per Data Files/1.md (9-cluster rollup).
CLUSTER_VIEW_ORDER = [
    "GCPL Consolidated",
    "GCPL India Cluster",
    "India Standalone",
    "Godrej Indonesia",
    "GAUM",
    "GAMC",
    "Godrej International (Kenya + Exports)",
    "LATAM- (Post Hyper)",
    "SAARC",
]

CURRENCY_ALIASES = {
    "₹": "INR", "rs": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR",
    "$": "USD", "usd": "USD", "dollar": "USD",
    "taka": "Taka", "bdt": "Taka", "tk": "Taka",
    "idr": "IDR", "rupiah": "IDR",
    "ngn": "NGN", "naira": "NGN",
    "ghs": "GHS", "cedi": "GHS",
    "kes": "KES", "ksh": "KES",
    "tzs": "TZS", "tzsh": "TZS",
    "zmw": "ZMW", "kwacha": "ZMW",
    "aed": "AED", "dhs": "AED", "dirham": "AED",
    "lkr": "LKR", "lkr ": "LKR",
    "arg": "Arg", "ars": "Arg", "peso": "Arg",
    "chile": "Chile", "clp": "Chile",
}

# Crore = 10M INR. Conversion factors TO Crore.
UNIT_TO_CRORE = {
    "crore": 1.0, "crs": 1.0, "cr": 1.0, "crs.": 1.0,
    "mn": 0.1, "million": 0.1,
    "billion": 100.0, "bn": 100.0,
    "peso million": 0.1,  # magnitude only; FX not applied
    "lakh": 0.01, "l": 0.01,
}

_METRIC_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_distincts() -> dict:
    for cand in [
        _repo_root() / "Data Files" / "distincts.json",
        Path("Data Files/distincts.json"),
        Path("distincts.json"),
    ]:
        if cand.exists():
            return json.loads(cand.read_text())
    return {}


@lru_cache(maxsize=1)
def load_region_aliases() -> dict:
    for cand in [
        Path(__file__).parent / "REGION_ALIASES.json",
        _repo_root() / "tools" / "REGION_ALIASES.json",
    ]:
        if cand.exists():
            return json.loads(cand.read_text())
    return {}


def all_db_regions() -> List[str]:
    return load_distincts().get("regions", [])


def region_currency_map() -> Dict[str, List[str]]:
    """DB-driven region -> [currencies] map (replaces hardcoded map)."""
    return load_distincts().get("region_currency_map", {})


def validate_metric(metric: str, table: str = "ftm") -> str:
    """Validate a metric identifier against frozen columns (anti-injection)."""
    if not _METRIC_RE.match(metric or ""):
        raise ValueError(f"Invalid metric name: {metric!r}")
    cols = load_distincts().get(table, {}).get("columns", [])
    if cols and metric not in cols:
        # allow margin pct siblings & generic names even if column list is stale
        if not (metric.endswith("_pct_nsv") or "/" in metric):
            raise ValueError(f"Unknown metric {metric!r} for table {table!r}")
    return metric


def validate_metrics(metrics: List[str], table: str = "ftm") -> List[str]:
    seen, out = set(), []
    for m in metrics or []:
        m = (m or "").strip()
        if m and m not in seen:
            validate_metric(m, table)
            seen.add(m)
            out.append(m)
    if not out:
        raise ValueError("No valid metrics supplied")
    return out


def resolve_region(user_text: str) -> List[str]:
    """Map free text to one or more DB region names.

    Priority: exact (case-insensitive) -> alias map -> substring match.
    Argentina always expands to both hyperinflation lines (a.md P3.3).
    """
    text = (user_text or "").strip()
    if not text:
        return []
    regions = all_db_regions()
    low = text.lower()

    # 1. exact
    for r in regions:
        if r.lower() == low:
            return _expand_argentina([r])

    # 2. alias map
    aliases = load_region_aliases()
    for alias, targets in aliases.items():
        if alias.lower() == low or alias.lower() in low:
            matched = [t for t in targets if t in regions]
            if matched:
                return _expand_argentina(matched)

    # 3. substring: collect every region containing the text or vice versa
    hits = [r for r in regions if low in r.lower() or r.lower() in low]
    if hits:
        # "india" alone is ambiguous -> return both India lines
        return _expand_argentina(hits)

    # 4. geographic shorthands
    geo = {
        "west africa": ["Nigeria", "Ghana"],
        "east africa": ["Africa East Cluster", "Kenya", "Kenya LC", "Tanzania"],
        "africa": ["Africa East Cluster", "Africa South Cluster"],
        "latam": [r for r in regions if "LATAM" in r],
        "all": regions, "global": regions, "every region": regions,
        "consolidated": ["GCPL Consolidated"],
    }
    for key, targets in geo.items():
        if key in low:
            return _expand_argentina([t for t in targets if t in regions])
    return []


def _expand_argentina(regions: List[str]) -> List[str]:
    if any("argentina" in r.lower() for r in regions) and len(regions) == 1 and "argentina" in regions[0].lower():
        pass  # single partial already handled by substring; ensure both lines
    out = list(regions)
    if any(a.lower() == "argentina" for a in regions):
        both = [r for r in all_db_regions() if "argentina" in r.lower()]
        out = [r for r in out if r.lower() != "argentina"] + both
    # if user typed bare "Argentina", substring already returns both; dedupe
    seen, ded = set(), []
    for r in out:
        if r not in seen:
            seen.add(r)
            ded.append(r)
    return ded


def resolve_currency(region: str, user_text: Optional[str] = None) -> str:
    """Resolve display currency: explicit alias > region default (LC-first).

    Defaults to the region's local (non-INR) currency when the DB holds one,
    else INR. This fixes the old map (LATAM->USD wrong, GAUM->USD wrong).
    """
    if user_text:
        code = CURRENCY_ALIASES.get(user_text.strip().lower() if len(user_text.strip()) <= 6 else user_text.strip().lower(), None)
        # also check symbols inside longer text
        if code:
            return code
        for alias, c in CURRENCY_ALIASES.items():
            if alias in user_text.lower():
                return c
        if user_text.strip().upper() in ("LC", "LOCAL"):
            pass  # fall through to local default
        elif len(user_text.strip()) <= 5 and user_text.strip().isalpha():
            return user_text.strip().upper() if user_text.strip().upper() != "BDT" else "Taka"
    cmap = region_currency_map()
    # exact region match first
    for db_region, currs in cmap.items():
        if db_region.lower() == (region or "").lower():
            non_inr = [c for c in currs if c != "INR"]
            return non_inr[0] if non_inr else "INR"
    # substring fallback
    for db_region, currs in cmap.items():
        if (region or "").lower() in db_region.lower() or db_region.lower() in (region or "").lower():
            non_inr = [c for c in currs if c != "INR"]
            return non_inr[0] if non_inr else "INR"
    return "INR"


def normalize_month(month: str) -> str:
    m = (month or "").strip()
    if m in MONTH_ORDER:
        return m
    key = m.lower()
    if key in MONTHS_FULL:
        return MONTHS_FULL[key]
    cap = m[:3].title()
    if cap in MONTH_ORDER:
        return cap
    raise ValueError(f"Unknown month: {month!r}")


def normalize_unit(value: Optional[float], unit: Optional[str]) -> Tuple[Optional[float], str, Optional[str]]:
    """Return (value_in_crores_or_original, display_unit, note).

    INR-family units convert to Crore for comparable views; anything else
    passes through with a flag so callers can label the source unit (a.md G20).
    """
    if value is None:
        return None, unit or "", None
    u = (unit or "").strip()
    factor = UNIT_TO_CRORE.get(u.lower())
    if factor is not None:
        return value * factor, "Crore", (f"source unit {u}" if u.lower() != "crore" else None)
    return value, u, f"non-standard unit preserved: {u}" if u else None


def infer_components(target_metric: str) -> List[str]:
    """Generic component inference from P&L hierarchy (a.md P1.5)."""
    if target_metric in FINANCIAL_HIERARCHY:
        return FINANCIAL_HIERARCHY[target_metric]
    if target_metric.endswith("_pct_nsv"):
        base = target_metric[: -len("_pct_nsv")]
        return [base, "net_sales_ind_as"]
    # fallback: decompose profitability via sales vs cost blocks
    return ["net_sales_ind_as", "cost_of_goods_sold", "total_a_p_spends", "total_fixed_overheads"]


def missing_data_message(requested: str, available: List[str]) -> str:
    return (
        f"N/A for {requested}: no rows in DB. "
        f"Nearest available: {', '.join(available[:6])}. Values are never hallucinated."
    )
