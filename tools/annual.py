"""
Phase 2 tool: FY / half-year reader (a.md P2.4, gaps G8/G9).
`half` is index-only by schema; FY carries val/aop/aop_iya lenses.
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import load_distincts
except ImportError:  # pragma: no cover
    from _helpers import load_distincts  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


@tool
def query_fy_half(
    table: str,
    region: str,
    metric: str,
    year: int,
    half: str = "H1",
    lens: str = "val",
    currency: str = "INR",
    extra_metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Full-year or half-year lookup.

    Examples:
    - "FY24 Net Sales for India?" -> table="fy", year=2024
    - "FY25 actual vs AOP?" -> lens="aop"
    - "H1 vs H2 2025 growth index?" -> table="half"

    Args:
        table: "fy" | "half"
        region/metric/year: Target
        half: H1|H2 (half table only)
        lens: val | aop | aop_iya (fy only)
        currency: Currency code
        extra_metrics: Extra base metrics in same call
    """
    if table not in ("fy", "half"):
        return {"success": False, "error": "table must be 'fy' or 'half'"}
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if table == "half":
            col = f"{metric}_aop_iya"
            allowed = set(load_distincts().get("half", {}).get("columns", []))
            if allowed and col not in allowed:
                return {"success": False, "error": f"Unknown half column {col}"}
            if half not in ("H1", "H2", "both"):
                return {"success": False, "error": "half must be H1|H2|both"}
            if half == "both":
                cur.execute(f'SELECT half, "{col}" AS idx, currency FROM half WHERE region=? AND year=? AND currency=?',
                            (region, year, currency))
                rows = cur.fetchall()
            else:
                cur.execute(f'SELECT half, "{col}" AS idx, currency FROM half WHERE region=? AND year=? AND half=? AND currency=?',
                            (region, year, half, currency))
                rows = cur.fetchall()
            conn.close()
            if not rows:
                return {"success": False, "error": f"No half rows for {region} {year} {half}"}
            return {"success": True, "table": "half", "region": region, "metric": metric,
                    "year": year, "rows": [dict(r) for r in rows],
                    "disclaimer": "half-year table carries growth index only; no absolutes."}
        # fy
        if lens not in ("val", "aop", "aop_iya"):
            return {"success": False, "error": "lens must be val|aop|aop_iya"}
        bases = [metric] + list(extra_metrics or [])
        bases = list(dict.fromkeys([b for b in bases if b]))
        cols = [f"{b}_{lens}" for b in bases]
        allowed = set(load_distincts().get("fy", {}).get("columns", []))
        unknown = [c for c in cols if allowed and c not in allowed]
        if unknown:
            return {"success": False, "error": f"Unknown fy columns: {unknown}"}
        sel = ", ".join([f'"{c}"' for c in cols])
        cur.execute(f'SELECT year, {sel}, currency FROM fy WHERE region=? AND year=? AND currency=? LIMIT 1',
                    (region, year, currency))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"success": False, "error": f"No FY row for {region} FY{year} [{currency}]",
                    "coverage_note": "fy covers 2023/2024/2025 sparsely."}
        return {"success": True, "table": "fy", "region": region, "year": year,
                "lens": lens, "currency": currency,
                "values": {b: row[c] for b, c in zip(bases, cols)}}
    except Exception as e:
        return {"success": False, "error": str(e), "table": table}
