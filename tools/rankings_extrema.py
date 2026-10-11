"""
Tool 3: Rankings & Extrema (Phase 1 rework per a.md P1.3)
- NULL-safe (WHERE metric IS NOT NULL)
- Margin-expression support: metric="ebitda/net_sales_ind_as"
- pnl_type='both' support
"""

import os
import sqlite3
from typing import Any, Dict, List

from langchain_core.tools import tool

try:
    from tools._helpers import MONTH_ORDER
except ImportError:  # pragma: no cover
    from _helpers import MONTH_ORDER  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


def _metric_expr(metric: str) -> str:
    metric = (metric or "").strip()
    if "/" in metric:  # margin expression
        num, den = [p.strip() for p in metric.split("/", 1)]
        if not num or not den:
            raise ValueError(f"Bad margin expression: {metric!r}")
        if not num.replace("_", "").isalnum() or not den.replace("_", "").isalnum():
            raise ValueError(f"Bad margin expression: {metric!r}")
        return f'(CAST("{num}" AS FLOAT) / NULLIF(CAST("{den}" AS FLOAT), 0) * 100.0)'
    if not metric.replace("_", "").isalnum():
        raise ValueError(f"Invalid metric: {metric!r}")
    return f'"{metric}"'


@tool
def find_rankings_extrema(
    region: str,
    metric: str,
    months: List[str],
    years: List[int],
    criteria: str = "maximum",
    pnl_type: str = "Reported",
    currency: str = "INR",
) -> Dict[str, Any]:
    """
    Find peak/valley months for a metric (or margin expression) across periods.

    Examples:
    - "Which month Oct 2024->Mar 2025 had peak EBITDA for India?"
    - "EBITDA margin rank across months" -> metric="ebitda/net_sales_ind_as"

    Args:
        region: Region name
        metric: Metric or "numerator/denominator" margin expression
        months: Month list e.g. ["Oct","Nov","Dec","Jan","Feb","Mar"]
        years: Year list e.g. [2024, 2025]
        criteria: maximum | minimum
        pnl_type: Reported | Organic | both
        currency: Currency code
    """
    db_path = _db_path()
    try:
        expr = _metric_expr(metric)
    except ValueError as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        mph = ",".join(["?"] * len(months))
        yph = ",".join(["?"] * len(years))
        direction = "DESC" if criteria == "maximum" else "ASC"
        if pnl_type == "both":
            pnl_clause, extra = "AND pnl_type IN ('Reported','Organic')", []
        else:
            pnl_clause, extra = "AND pnl_type = ?", [pnl_type]
        sql = f"""SELECT month, year, {expr} AS metric_value, unit, currency, pnl_type
                  FROM ftm WHERE region = ? AND month IN ({mph}) AND year IN ({yph})
                  AND currency = ? {pnl_clause} AND {expr} IS NOT NULL
                  ORDER BY metric_value {direction}, year DESC,
                  CASE month WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                  WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                  WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                  WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12 END DESC"""
        cursor.execute(sql, [region] + months + years + [currency] + extra)
        rows = cursor.fetchall()
        if not rows:
            return {"success": False,
                    "error": f"No non-null data for {region} in periods (NULLs excluded).",
                    "metric": metric, "region": region}
        ext = rows[0]
        rankings = [{"rank": i + 1, "month": r["month"], "year": r["year"],
                     "period": f"{r['month']} {r['year']}", "value": r["metric_value"],
                     "pnl_type": r["pnl_type"]} for i, r in enumerate(rows)]
        ctx: Dict[str, Any] = {}
        if len(rows) >= 2 and rows[1]["metric_value"]:
            imp = ext["metric_value"] - rows[1]["metric_value"]
            ctx = {"second_best_period": f"{rows[1]['month']} {rows[1]['year']}",
                   "second_best_value": rows[1]["metric_value"], "improvement": imp,
                   "improvement_pct": (imp / rows[1]["metric_value"] * 100)}
        conn.close()
        return {"success": True, "metric": metric, "region": region, "criteria": criteria,
                "extreme": {"month": ext["month"], "year": ext["year"],
                            "period": f"{ext['month']} {ext['year']}",
                            "value": ext["metric_value"], "unit": ext["unit"],
                            "currency": ext["currency"], "pnl_type": ext["pnl_type"]},
                "all_rankings": rankings, "context": ctx,
                "pnl_type": pnl_type, "total_periods_analyzed": len(rows),
                "nulls_excluded": True,
                "generated_sql": " ".join(sql.split())}
    except Exception as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}
