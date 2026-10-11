"""
Phase 2 tool: QTD/YTD cumulative reader (a.md P2.1, gaps G1/G2/G3/G4).
Reads `qtd` / `ytd` tables with val | aop | aop_iya lenses.
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import load_distincts, normalize_month
except ImportError:  # pragma: no cover
    from _helpers import load_distincts, normalize_month  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


def _lens_suffix(table: str, lens: str) -> str:
    if table == "qtd":
        return {"val": "_qtd_val", "aop": "_qtd_aop", "aop_iya": "_qtd_aop_iya"}[lens]
    return {"val": "__val", "aop": "__aop", "aop_iya": "__aop_iya"}[lens]


@tool
def query_qtd_ytd(
    table: str,
    region: str,
    metric: str,
    month: str,
    year: int,
    lens: str = "val",
    pnl_type: str = "Reported",
    currency: str = "INR",
    extra_metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Read cumulative QTD/YTD values, budgets (AOP), or YoY indices.

    Use for "to date" questions the old ftm-only tools could not answer.

    Examples:
    - "QTD Net Sales for Mar 2025 India?" -> table="qtd", lens="val"
    - "YTD EBITDA Mar 2025 vs budget?" -> table="ytd", lens="aop"
    - "QTD A&P Dec 2024 vs last year?" -> lens="aop_iya"

    Args:
        table: "qtd" | "ytd"
        region: Region name
        metric: Base metric e.g. "net_sales_ind_as"
        month/year: Period (qtd/ytd cover Oct-Dec 2024 + Jan-Mar 2025)
        lens: "val" (actual) | "aop" (budget) | "aop_iya" (index)
        pnl_type/currency: Filters
        extra_metrics: Extra base metrics in same call
    """
    if table not in ("qtd", "ytd"):
        return {"success": False, "error": "table must be 'qtd' or 'ytd'"}
    if lens not in ("val", "aop", "aop_iya"):
        return {"success": False, "error": "lens must be val|aop|aop_iya"}
    suffix = _lens_suffix(table, lens)
    bases = [metric] + list(extra_metrics or [])
    bases = list(dict.fromkeys([b for b in bases if b]))
    cols = [f"{b}{suffix}" for b in bases]
    pct_cols = [f"{b}{suffix.replace('_val', '_pct_nsv')}" for b in bases] if lens == "val" else []
    try:
        month = normalize_month(month)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    allowed = set(load_distincts().get(table, {}).get("columns", []))
    unknown = [c for c in cols if allowed and c not in allowed]
    if unknown:
        return {"success": False, "error": f"Unknown columns for {table}: {unknown}",
                "hint": "Check Data Files/distincts.json for valid lenses."}
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        sel = ", ".join([f'"{c}"' for c in cols + [p for p in pct_cols if p in allowed]])
        sql = (f'SELECT region, {sel}, currency, pnl_type, month, year FROM "{table}" '
               'WHERE region=? AND month=? AND year=? AND currency=? AND pnl_type=? LIMIT 1')
        cur.execute(sql, (region, month, year, currency, pnl_type))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"success": False,
                    "error": f"No {table.upper()} row for {region} {month} {year} [{currency}/{pnl_type}]",
                    "table": table, "lens": lens,
                    "coverage_note": "qtd/ytd cover Oct-Dec 2024 + Jan-Mar 2025 only."}
        values = {b: row[c] for b, c in zip(bases, cols)}
        out: Dict[str, Any] = {"success": True, "table": table, "lens": lens,
                               "region": region, "period": f"{month} {year}",
                               "currency": currency, "pnl_type": pnl_type,
                               "values": values, "generated_sql": " ".join(sql.split())}
        pcts = {b: row[p] for b, p in zip(bases, pct_cols) if p in allowed and row[p] is not None}
        if pcts:
            out["pct_nsv"] = pcts
        return out
    except Exception as e:
        return {"success": False, "error": str(e), "table": table}
