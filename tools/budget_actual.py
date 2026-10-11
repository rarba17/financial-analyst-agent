"""
Phase 2 tool: budget/actual variance reader (a.md P2.2, gaps G3/G6/G7).
Handles qtd | ytd | quarter | fy. `quarter` is budget-only by schema design:
actuals are refused with a disclaimer + ftm-sum estimate offer.
"""

import os
import sqlite3
from typing import Any, Dict

from langchain_core.tools import tool

try:
    from tools._helpers import load_distincts, normalize_month
except ImportError:  # pragma: no cover
    from _helpers import load_distincts, normalize_month  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


_SUFFIX = {
    "qtd": ("_qtd_val", "_qtd_aop"),
    "ytd": ("__val", "__aop"),
    "fy": ("_val", "_aop"),
    "quarter": (None, "_aop"),
}


@tool
def query_budget_variance(
    table: str,
    region: str,
    metric: str,
    month: str = "Mar",
    year: int = 2025,
    quarter: str = "Q1",
    pnl_type: str = "Reported",
    currency: str = "INR",
) -> Dict[str, Any]:
    """
    Actual vs budget (AOP) variance with gap ABS + gap %.

    Examples:
    - "Actual vs budget NSV Mar 2025 QTD/YTD?"
    - "Q3 budget NSV 2024 India?" (table="quarter")
    - "FY25 actual vs AOP?"

    Args:
        table: qtd | ytd | quarter | fy
        region/metric: What to compare
        month/year: Period for qtd/ytd/fy (fy ignores month)
        quarter: Q1|Q2|Q3 for table="quarter" (no Q4 in DB)
        pnl_type/currency: Filters
    """
    if table not in _SUFFIX:
        return {"success": False, "error": "table must be qtd|ytd|quarter|fy"}
    val_suf, aop_suf = _SUFFIX[table]
    actual_col = f"{metric}{val_suf}" if val_suf else None
    budget_col = f"{metric}{aop_suf}"
    allowed = set(load_distincts().get(table, {}).get("columns", []))
    if allowed and budget_col not in allowed:
        return {"success": False, "error": f"Unknown budget column {budget_col} for {table}"}
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if table == "quarter":
            if quarter not in ("Q1", "Q2", "Q3"):
                return {"success": False, "error": "quarter must be Q1|Q2|Q3 (no Q4 in DB)",
                        "disclaimer": "quarter table holds budgets only; actuals do not exist."}
            cur.execute(
                f'SELECT region, "{budget_col}" AS budget, currency, year, quarter FROM "quarter" '
                'WHERE region=? AND quarter=? AND year=? AND currency=? LIMIT 1',
                (region, quarter, year, currency),
            )
            row = cur.fetchone()
            conn.close()
            if not row:
                return {"success": False, "error": f"No quarter budget for {region} {quarter} {year}"}
            return {
                "success": True, "table": table, "region": region, "metric": metric,
                "period": f"{quarter} {year}", "budget": row["budget"],
                "actual": None, "gap_abs": None, "gap_pct": None,
                "currency": currency,
                "disclaimer": ("quarter table is budget-only (no actuals by schema). "
                               "'Q actuals' should be answered N/A + offer an ftm month-sum estimate with disclaimer."),
                "generated_sql": f'SELECT "{budget_col}" FROM quarter WHERE region/quarter/year/currency match',
            }
        if table == "fy":
            cur.execute(
                f'SELECT "{actual_col}" AS actual, "{budget_col}" AS budget, currency, year '
                'FROM fy WHERE region=? AND year=? AND currency=? LIMIT 1',
                (region, year, currency),
            )
            period = f"FY{year}"
        else:
            month = normalize_month(month)
            cur.execute(
                f'SELECT region, "{actual_col}" AS actual, "{budget_col}" AS budget, currency, pnl_type '
                f'FROM "{table}" WHERE region=? AND month=? AND year=? AND currency=? AND pnl_type=? LIMIT 1',
                (region, month, year, currency, pnl_type),
            )
            period = f"{month} {year}"
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"success": False, "error": f"No {table} row for {region} {period}"}
        actual, budget = row["actual"], row["budget"]
        gap = (actual - budget) if (actual is not None and budget is not None) else None
        return {"success": True, "table": table, "region": region, "metric": metric,
                "period": period, "actual": actual, "budget": budget,
                "gap_abs": gap,
                "gap_pct": (gap / budget * 100) if (gap is not None and budget) else None,
                "currency": currency, "pnl_type": pnl_type if table != "fy" else None}
    except Exception as e:
        return {"success": False, "error": str(e), "table": table}
