"""
Phase 2 tool: YoY growth reader (a.md P2.3, gaps G4/G5).
Reads *_iya where present, else computes (curr - sply) / sply.
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


_IYA_SUFFIX = {"ftm": "_pct_nsv", "qtd": "_qtd_iya", "ytd": "__iya", "fy": "_aop_iya", "half": "_aop_iya"}
_VAL_COL = {"ftm": "{m}", "qtd": "{m}_qtd_val", "ytd": "{m}__val", "fy": "{m}_val"}


@tool
def query_yoy_growth(
    table: str,
    region: str,
    metric: str,
    month: str = "Mar",
    year: int = 2025,
    pnl_type: str = "Reported",
    currency: str = "INR",
) -> Dict[str, Any]:
    """
    YoY growth for a metric: prefer stored index, else compute vs SPLY.

    Examples:
    - "NSV Dec 2024 vs Dec 2023 for India?"
    - "EBITDA Mar 2025 vs Mar 2024 YoY %?"
    - "H1 vs H2 2025 growth index?" (table="half" carries index only)

    Args:
        table: ftm | qtd | ytd | fy | half
        region/metric/month/year: Target cell (half ignores month)
        pnl_type/currency: Filters (half/fy ignore pnl_type)
    """
    if table not in ("ftm", "qtd", "ytd", "fy", "half"):
        return {"success": False, "error": "table must be ftm|qtd|ytd|fy|half"}
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cols = set(load_distincts().get(table, {}).get("columns", []))

        if table == "half":
            col = f"{metric}_aop_iya"
            cur.execute(f'SELECT year, half, "{col}" AS idx FROM half WHERE region=? AND year=? AND currency=?',
                        (region, year, currency))
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return {"success": False, "error": f"No half rows for {region} {year}",
                        "disclaimer": "half table is index-only; no absolutes exist."}
            return {"success": True, "table": table, "region": region, "metric": metric,
                    "year": year, "index_rows": [dict(r) for r in rows],
                    "method": "stored_index_only",
                    "disclaimer": "half-year carries growth index only."}

        month = normalize_month(month)
        # 1) try stored iya column
        iya_col = None
        for cand in ([f"{metric}{_IYA_SUFFIX[table]}"] if table != "ftm" else []):
            if not cols or cand in cols:
                iya_col = cand
                break
        stored = None
        if iya_col:
            where = "region=? AND month=? AND year=? AND currency=? AND pnl_type=?" if table in ("qtd", "ytd") \
                else "region=? AND year=? AND currency=?" if table == "fy" else None
            if where:
                params = (region, month, year, currency, pnl_type) if table in ("qtd", "ytd") else (region, year, currency)
                try:
                    cur.execute(f'SELECT "{iya_col}" AS idx FROM "{table}" WHERE {where} LIMIT 1', params)
                    r = cur.fetchone()
                    stored = r["idx"] if r else None
                except Exception:
                    stored = None

        # 2) compute vs SPLY from value columns
        computed = None
        if table in _VAL_COL:
            vcol = _VAL_COL[table].format(m=metric)
            try:
                if table == "ftm":
                    cur.execute(f'SELECT "{vcol}" AS v FROM ftm WHERE region=? AND month=? AND year=? AND currency=? AND pnl_type=? LIMIT 1',
                                (region, month, year, currency, pnl_type))
                    curr = cur.fetchone()
                    cur.execute(f'SELECT "{vcol}" AS v FROM ftm WHERE region=? AND month=? AND year=? AND currency=? AND pnl_type=? LIMIT 1',
                                (region, month, year - 1, currency, pnl_type))
                    prev = cur.fetchone()
                elif table in ("qtd", "ytd"):
                    cur.execute(f'SELECT "{vcol}" AS v FROM "{table}" WHERE region=? AND month=? AND year=? AND currency=? AND pnl_type=? LIMIT 1',
                                (region, month, year, currency, pnl_type))
                    curr = cur.fetchone()
                    cur.execute(f'SELECT "{vcol}" AS v FROM "{table}" WHERE region=? AND month=? AND year=? AND currency=? AND pnl_type=? LIMIT 1',
                                (region, month, year - 1, currency, pnl_type))
                    prev = cur.fetchone()
                else:  # fy
                    cur.execute(f'SELECT "{vcol}" AS v FROM fy WHERE region=? AND year=? AND currency=? LIMIT 1', (region, year, currency))
                    curr = cur.fetchone()
                    cur.execute(f'SELECT "{vcol}" AS v FROM fy WHERE region=? AND year=? AND currency=? LIMIT 1', (region, year - 1, currency))
                    prev = cur.fetchone()
                if curr and prev and curr["v"] is not None and prev["v"]:
                    computed = {"current": curr["v"], "sply": prev["v"],
                                "abs_change": curr["v"] - prev["v"],
                                "yoy_pct": (curr["v"] - prev["v"]) / prev["v"] * 100}
            except Exception:
                computed = None
        conn.close()
        if stored is None and computed is None:
            return {"success": False, "error": f"No YoY basis for {region} {month} {year} ({table})",
                    "metric": metric}
        return {"success": True, "table": table, "region": region, "metric": metric,
                "period": f"{month} {year}", "stored_index": stored,
                "computed_sply": computed,
                "method": "stored_index" if stored is not None else "computed_sply"}
    except Exception as e:
        return {"success": False, "error": str(e)}
