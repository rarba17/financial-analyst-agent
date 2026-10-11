"""
Phase 2 tool: first-class margins (a.md P2.6, gap G14).
Returns numerator ABS + denominator ABS + % together (per Data Files/1.md rule).
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import normalize_month
except ImportError:  # pragma: no cover
    from _helpers import normalize_month  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


@tool
def query_margin(
    numerator: str,
    denominator: str,
    region: str,
    month: str,
    year: int,
    pnl_type: str = "Reported",
    currency: str = "INR",
    regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Margin/ratio with ABS legs + % in one call.

    Examples:
    - "EBITDA margin India Dec 2024" -> numerator="ebitda", denominator="net_sales_ind_as"
    - "EBITDA margin rank across regions" -> pass regions=[...]

    Args:
        numerator/denominator: Base metric columns
        region: Single region (ignored if regions given)
        month/year: Period
        pnl_type/currency: Filters
        regions: Optional multi-region rank in one call
    """
    for m in (numerator, denominator):
        if not (m or "").replace("_", "").isalnum():
            return {"success": False, "error": f"Invalid metric: {m!r}"}
    try:
        month = normalize_month(month)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    rlist = regions or [region]
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rph = ",".join(["?"] * len(rlist))
        sql = f"""SELECT region, "{numerator}" AS num, "{denominator}" AS den, unit, currency, pnl_type,
                  (CAST("{numerator}" AS FLOAT)/NULLIF(CAST("{denominator}" AS FLOAT),0)*100.0) AS pct
                  FROM ftm WHERE region IN ({rph}) AND month=? AND year=? AND currency=? AND pnl_type=?
                  ORDER BY pct DESC"""
        cur.execute(sql, rlist + [month, year, currency, pnl_type])
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return {"success": False, "error": f"No data for margin {numerator}/{denominator} {month} {year}"}
        out_rows = [{"region": r["region"], "numerator": r["num"], "denominator": r["den"],
                     "margin_pct": r["pct"], "unit": r["unit"], "currency": r["currency"],
                     "pnl_type": r["pnl_type"]} for r in rows]
        return {"success": True, "numerator": numerator, "denominator": denominator,
                "period": f"{month} {year}", "currency": currency, "pnl_type": pnl_type,
                "rows": out_rows, "leader": out_rows[0],
                "presentation_rule": "Always show numerator ABS + denominator ABS + % together.",
                "generated_sql": " ".join(sql.split())}
    except Exception as e:
        return {"success": False, "error": str(e)}
