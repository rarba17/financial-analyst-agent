"""
Tool 2: Time Series Analysis Tool (Phase 1 rework per a.md P1.2)
- Adds analysis_type='yoy_sply' (same month prior year from ftm)
- Always attaches SPLY delta alongside MoM (per Data Files/1.md)
- Multi-metric support via `metrics` list
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import MONTH_ORDER, normalize_month, validate_metrics
except ImportError:  # pragma: no cover
    from _helpers import MONTH_ORDER, normalize_month, validate_metrics  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


def _period_list(start_month: str, start_year: int, end_month: str, end_year: int):
    start_month, end_month = normalize_month(start_month), normalize_month(end_month)
    ordered = sorted(MONTH_ORDER, key=MONTH_ORDER.get)
    out: List[tuple] = []
    if start_year == end_year:
        s, e = MONTH_ORDER[start_month], MONTH_ORDER[end_month]
        if s > e:
            raise ValueError("start must be <= end within same year")
        out = [(m, start_year) for m in ordered if s <= MONTH_ORDER[m] <= e]
    else:
        out = [(m, start_year) for m in ordered if MONTH_ORDER[m] >= MONTH_ORDER[start_month]]
        for y in range(start_year + 1, end_year):
            out += [(m, y) for m in ordered]
        out += [(m, end_year) for m in ordered if MONTH_ORDER[m] <= MONTH_ORDER[end_month]]
    return out


@tool
def analyze_time_series(
    region: str,
    metric: str,
    start_month: str,
    start_year: int,
    end_month: str,
    end_year: int,
    analysis_type: str = "mom_change",
    pnl_type: str = "Reported",
    currency: str = "INR",
    metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Analyze metric changes over time with MoM, trend, rolling avg, total change, YoY/SPLY.

    Examples:
    - "MoM change in EBITDA Feb->Mar 2025 for India?"
    - "NSV Dec 2024 vs Dec 2023 (SPLY) for India?"
    - "Net Sales trend Oct 2024->Mar 2025 for Indonesia"

    Args:
        region: Region name
        metric: Primary metric
        start_month/start_year/end_month/end_year: Window (cross-year OK)
        analysis_type: mom_change | rolling_avg | trend | total_change | yoy_sply
        pnl_type: Reported | Organic | both
        currency: Currency code
        metrics: Optional extra metrics fetched in same query

    Returns:
        Time series + requested analysis + always-on SPLY delta when prior-year data exists.
    """
    metric_list = [metric] + list(metrics or [])
    metric_list = list(dict.fromkeys([m for m in metric_list if m]))
    try:
        cols = validate_metrics(metric_list, "ftm")
    except ValueError as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}

    try:
        periods = _period_list(start_month, start_year, end_month, end_year)
    except ValueError as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}

    db_path = _db_path()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        select_list = ", ".join([f'"{c}" AS "{c}"' for c in cols])
        pairs = " OR ".join(["(month = ? AND year = ?)"] * len(periods))
        flat: List[Any] = []
        for m, y in periods:
            flat += [m, y]
        if pnl_type == "both":
            sql = f"""SELECT month, year, {select_list}, unit, currency, pnl_type FROM ftm
                      WHERE region = ? AND ({pairs}) AND currency = ?
                      AND pnl_type IN ('Reported','Organic')
                      ORDER BY pnl_type, year,
                      CASE month WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                      WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                      WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                      WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12 END"""
            params: List[Any] = [region] + flat + [currency]
        else:
            sql = f"""SELECT month, year, {select_list}, unit, currency, pnl_type FROM ftm
                      WHERE region = ? AND ({pairs}) AND currency = ? AND pnl_type = ?
                      ORDER BY year,
                      CASE month WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                      WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                      WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                      WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12 END"""
            params = [region] + flat + [currency, pnl_type]
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if not rows:
            return {"success": False, "error": f"No data for {region} in window.",
                    "metric": metric, "region": region,
                    "generated_sql_query": " ".join(sql.split())}

        def row_series(pnl: Optional[str]):
            subset = [r for r in rows if pnl is None or r["pnl_type"] == pnl]
            return [
                {"month": r["month"], "year": r["year"],
                 "period": f"{r['month']} {r['year']}",
                 "values": {c: r[c] for c in cols},
                 "value": r[cols[0]],
                 "unit": r["unit"], "currency": r["currency"]}
                for r in subset
            ]

        result: Dict[str, Any] = {
            "success": True, "metric": metric, "metrics": cols,
            "region": region, "unit": rows[0]["unit"], "currency": rows[0]["currency"],
            "pnl_type": pnl_type,
            "generated_sql_query": " ".join(sql.split()),
            "row_count": len(rows),
        }
        series_all = row_series(None if pnl_type != "both" else "__none__")
        if pnl_type == "both":
            rep, org = row_series("Reported"), row_series("Organic")
            result["reported_time_series"] = rep
            result["organic_time_series"] = org
            primary = rep
        else:
            primary = row_series(None)
            result["time_series"] = primary

        # --- requested analyses (primary metric) ---
        vals = [p["value"] for p in primary if p["value"] is not None]
        if analysis_type == "mom_change" and len(primary) >= 2:
            a, b = primary[-2], primary[-1]
            if a["value"] is not None and b["value"] is not None:
                chg = b["value"] - a["value"]
                result["mom_change"] = {
                    "from_period": a["period"], "to_period": b["period"],
                    "from_value": a["value"], "to_value": b["value"],
                    "absolute_change": chg,
                    "percentage_change": (chg / a["value"] * 100) if a["value"] else 0,
                    "direction": "increase" if chg > 0 else "decrease" if chg < 0 else "flat",
                }
        elif analysis_type == "rolling_avg" and len(vals) >= 2:
            n = min(3, len(vals))
            result["rolling_average"] = {
                "window_size": n,
                "periods_included": [p["period"] for p in primary[-n:]],
                "average": sum(vals[-n:]) / n,
            }
        elif analysis_type == "trend" and len(primary) >= 2:
            f, l = primary[0]["value"], primary[-1]["value"]
            ups = sum(1 for i in range(1, len(primary))
                      if (primary[i]["value"] or 0) > (primary[i - 1]["value"] or 0))
            downs = sum(1 for i in range(1, len(primary))
                        if (primary[i]["value"] or 0) < (primary[i - 1]["value"] or 0))
            result["trend"] = {
                "direction": "increasing" if ups > downs else "decreasing" if downs > ups else "stable",
                "start_value": f, "end_value": l,
                "total_change": (l - f) if f is not None and l is not None else None,
                "up_months": ups, "down_months": downs,
            }
        elif analysis_type == "total_change" and len(primary) >= 2:
            f, l = primary[0], primary[-1]
            if f["value"] is not None and l["value"] is not None:
                chg = l["value"] - f["value"]
                result["total_change"] = {
                    "start_period": f["period"], "end_period": l["period"],
                    "start_value": f["value"], "end_value": l["value"],
                    "absolute_change": chg,
                    "percentage_change": (chg / f["value"] * 100) if f["value"] else 0,
                }

        # --- always-on SPLY (a.md G5 / 1.md rule) ---
        sply = None
        try:
            last = primary[-1]
            cursor.execute(
                f'SELECT {cols[0]} AS v, unit FROM ftm WHERE region=? AND month=? AND year=? '
                'AND currency=? AND pnl_type=? LIMIT 1',
                (region, last["month"], last["year"] - 1, currency,
                 pnl_type if pnl_type != "both" else "Reported"),
            )
            prow = cursor.fetchone()
            if prow and prow["v"] is not None and last["value"] is not None:
                chg = last["value"] - prow["v"]
                sply = {"sply_period": f"{last['month']} {last['year'] - 1}",
                        "sply_value": prow["v"], "current_value": last["value"],
                        "absolute_change": chg,
                        "yoy_pct": (chg / prow["v"] * 100) if prow["v"] else 0}
        except Exception:
            sply = None
        result["sply_comparison"] = sply
        if analysis_type == "yoy_sply":
            if sply:
                result["yoy_sply"] = sply
            else:
                result["yoy_sply"] = None
                result["yoy_note"] = (
                    f"No SPLY row for {primary[-1]['month']} {primary[-1]['year'] - 1}; "
                    "in-coverage SPLY only for Oct-Dec 2023 / Jan-Mar 2024."
                )

        conn.close()
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "metric": metric, "region": region}
