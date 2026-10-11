"""
Tool 1: Basic Metrics Tool (Phase 1 rework per a.md P1.1)
- DB-driven currency map (distincts.json) instead of hardcoded map
- Region alias + LIKE fallback instead of exact-only match
- Multi-metric wide-fetch in one SQL (siblings in a single call)
- pnl_type='both' default preserved; _pct_nsv sibling auto-included on margin asks
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import (
        load_distincts,
        normalize_month,
        normalize_unit,
        resolve_currency,
        resolve_region,
        validate_metrics,
    )
except ImportError:  # pragma: no cover - direct script import
    from _helpers import (  # type: ignore
        load_distincts,
        normalize_month,
        normalize_unit,
        resolve_currency,
        resolve_region,
        validate_metrics,
    )


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


def _resolve_db_region(cursor, region: str):
    """Exact -> alias list -> LIKE fallback. Returns (db_region, tried)."""
    tried = [region]
    # alias expansion
    aliased = resolve_region(region)
    candidates: List[str] = []
    if aliased:
        candidates.extend(aliased)
        tried.extend(aliased)
    if region not in candidates:
        candidates.insert(0, region)
    for cand in candidates:
        cursor.execute("SELECT DISTINCT region FROM ftm WHERE region = ? LIMIT 1", (cand,))
        row = cursor.fetchone()
        if row:
            return row["region"], tried
    # LIKE fallback
    cursor.execute("SELECT DISTINCT region FROM ftm WHERE region LIKE ? LIMIT 5", (f"%{region}%",))
    rows = cursor.fetchall()
    if rows:
        tried.extend([r["region"] for r in rows])
        return rows[0]["region"], tried
    return None, tried


@tool
def query_basic_metrics(
    region: str,
    metric: str,
    month: str,
    year: int,
    pnl_type: str = "both",
    currency: str = "auto",
    metrics: Optional[List[str]] = None,
    include_pct_nsv: bool = True,
) -> Dict[str, Any]:
    """
    Retrieve one or more metric values for a specific period and region.

    Use this tool when the user asks for simple, point-in-time values.

    Examples:
    - "What was India's Net Sales in December 2024?"
    - "Show consolidated EBITDA for March 2025"
    - "Give me Total + Domestic + Export sales for India Dec 2024"

    Args:
        region: Region name (aliases accepted: "India" -> India lines, "LATAM", etc.)
        metric: Primary metric (e.g., "net_sales_ind_as", "ebitda")
        month: Month name (e.g., "Dec", "December")
        year: Year (e.g., 2024, 2025)
        pnl_type: "Reported", "Organic", or "both" (default "both")
        currency: Currency code, "auto" (local default), or "LC"
        metrics: Optional extra sibling metrics for wide-fetch in ONE sql call
        include_pct_nsv: Auto-fetch {metric}_pct_nsv sibling when present

    Returns:
        Dictionary with per-metric Reported/Organic values + units.
    """
    db_path = _db_path()
    wanted = [metric] + list(metrics or [])
    # de-dupe preserving order
    seen, metric_list = set(), []
    for m in wanted:
        if m and m not in seen:
            seen.add(m)
            metric_list.append(m)

    try:
        cols = validate_metrics(metric_list, "ftm")
    except ValueError as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}

    try:
        month = normalize_month(month)
    except ValueError as e:
        return {"success": False, "error": str(e), "region": region}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        db_region, tried = _resolve_db_region(cursor, region)
        if not db_region:
            return {
                "success": False,
                "error": f"No region match for {region!r}. Tried: {tried}. Check Data Files/distincts.json.",
                "metric": metric,
                "region": region,
                "regions_tried": tried,
            }

        if currency in ("auto", "LC", "local", None):
            currency = resolve_currency(db_region, None if currency == "auto" else currency)

        # auto-include _pct_nsv siblings for margin-style queries
        ftm_cols = set(load_distincts().get("ftm", {}).get("columns", []))
        fetch_cols = list(cols)
        pct_map: Dict[str, str] = {}
        if include_pct_nsv:
            for c in cols:
                pct = f"{c}_pct_nsv"
                if pct in ftm_cols and pct not in fetch_cols:
                    fetch_cols.append(pct)
                    pct_map[c] = pct

        select_list = ", ".join([f'"{c}"' for c in fetch_cols])
        pnl_filter = "AND pnl_type IN ('Reported', 'Organic')" if pnl_type == "both" else "AND pnl_type = ?"
        sql = f"""
            SELECT region, {select_list}, unit, currency, pnl_type, month, year
            FROM ftm
            WHERE region = ? AND month = ? AND year = ? AND currency = ?
            {pnl_filter}
            ORDER BY pnl_type DESC
        """
        params: List[Any] = [db_region, month, year, currency]
        if pnl_type != "both":
            params.append(pnl_type)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if not rows:
            return {
                "success": False,
                "error": f"No data for {db_region} in {month} {year} [{currency}/{pnl_type}]",
                "metric": metric,
                "region": db_region,
                "requested_region": region,
                "period": f"{month} {year}",
                "currency_used": currency,
                "generated_sql": " ".join(sql.split()),
            }

        by_pnl: Dict[str, Dict[str, Any]] = {}
        unit = rows[0]["currency"] and rows[0]["unit"]
        for row in rows:
            by_pnl[row["pnl_type"]] = {c: row[c] for c in fetch_cols}

        values: Dict[str, Any] = {}
        for c in cols:
            entry: Dict[str, Any] = {}
            for pnl in ("Reported", "Organic"):
                if pnl in by_pnl:
                    raw = by_pnl[pnl][c]
                    norm_val, norm_unit, note = normalize_unit(raw, rows[0]["unit"])
                    entry[pnl.lower()] = {
                        "value": raw,
                        "value_crore": norm_val,
                        "unit": rows[0]["unit"],
                        "display_unit": norm_unit,
                        "unit_note": note,
                    }
                    if c in pct_map and by_pnl[pnl].get(pct_map[c]) is not None:
                        entry[pnl.lower()]["pct_nsv"] = by_pnl[pnl][pct_map[c]]
            values[c] = entry

        conn.close()
        return {
            "success": True,
            "metrics": values,
            "metric": metric,  # backward compat
            "reported_value": values.get(metric, {}).get("reported", {}).get("value"),
            "organic_value": values.get(metric, {}).get("organic", {}).get("value"),
            "unit": rows[0]["unit"],
            "currency": currency,
            "region": db_region,
            "requested_region": region,
            "period": f"{month} {year}",
            "pnl_types_returned": sorted(by_pnl.keys()),
            "generated_sql": " ".join(sql.split()),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}
