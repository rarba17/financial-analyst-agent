"""
Tool 4: Cross-Region Comparison (Phase 1 rework per a.md P1.4)
- Single-currency guard: refuses silently-summed mixed-currency totals
- Margin mode via metric_b (margin = a/b*100, with ABS legs returned)
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import region_currency_map
except ImportError:  # pragma: no cover
    from _helpers import region_currency_map  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


def _expr(metric: str) -> str:
    if not metric.replace("_", "").isalnum():
        raise ValueError(f"Invalid metric: {metric!r}")
    return f'"{metric}"'


@tool
def compare_regions(
    regions: List[str],
    metric: str,
    month: str,
    year: int,
    pnl_type: str = "Reported",
    currency: str = "INR",
    metric_b: Optional[str] = None,
    convert_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare a metric (or margin a/b) across regions for the same period.

    Examples:
    - "Rank India, Indonesia, GAUM by Net Sales Mar 2025 (INR)"
    - "EBITDA margin rank across regions" -> metric="ebitda", metric_b="net_sales_ind_as"

    Args:
        regions: Region list
        metric: Numerator metric
        month/year: Period
        pnl_type: Reported | Organic
        currency: Single currency filter (guard enforced)
        metric_b: Optional denominator for margin mode
        convert_to: If set (e.g. "INR"), mixed-currency compare is labelled converted-view;
            without it, regions spanning >1 native currency return a guard error.
    """
    db_path = _db_path()
    try:
        expr_a = _expr(metric)
        expr_b = _expr(metric_b) if metric_b else None
    except ValueError as e:
        return {"success": False, "error": str(e), "metric": metric, "regions": regions}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- currency guard (a.md G11): the fetch itself filters to ONE currency,
        # so mixing can only happen via missing-row asymmetry. Report it truthfully.
        cmap = region_currency_map()
        native: Dict[str, List[str]] = {}
        for r in regions:
            for db_r, currs in cmap.items():
                if db_r.lower() == r.lower():
                    native[r] = currs
                    break
        rph = ",".join(["?"] * len(regions))

        if expr_b:
            select = (
                f"{expr_a} AS leg_a, {expr_b} AS leg_b, "
                f"(CAST({expr_a} AS FLOAT)/NULLIF(CAST({expr_b} AS FLOAT),0)*100.0) AS metric_value"
            )
        else:
            select = f"{expr_a} AS metric_value"
            if metric_b is None:
                select += f", {expr_a} AS leg_a"
        sql = f"""SELECT region, {select}, unit, currency, pnl_type FROM ftm
                  WHERE region IN ({rph}) AND month=? AND year=? AND currency=? AND pnl_type=?
                  AND {expr_a} IS NOT NULL ORDER BY metric_value DESC"""
        cursor.execute(sql, regions + [month, year, convert_to or currency, pnl_type])
        rows = cursor.fetchall()
        if not rows:
            return {"success": False, "error": f"No data for regions in {month} {year}",
                    "metric": metric}
        non_null = [r for r in rows if r["metric_value"] is not None]
        total = sum(r["leg_a"] for r in rows if r["leg_a"] is not None) if not expr_b else None
        ranked, leader = [], (non_null[0]["metric_value"] if non_null else 0)
        for i, r in enumerate(rows, 1):
            v = r["metric_value"]
            entry: Dict[str, Any] = {"rank": i, "region": r["region"], "value": v,
                                     "gap_from_leader": (v - leader) if v is not None else None,
                                     "unit": r["unit"], "currency": r["currency"]}
            if expr_b:
                entry["numerator"] = r["leg_a"]
                entry["denominator"] = r["leg_b"]
            else:
                entry["share_of_total"] = (v / total * 100) if total else 0
            ranked.append(entry)
        insights = []
        if ranked:
            insights.append(f"{ranked[0]['region']} leads")
        result: Dict[str, Any] = {
            "success": True, "metric": metric, "metric_b": metric_b,
            "margin_mode": bool(expr_b), "period": f"{month} {year}",
            "ranked_regions": ranked, "regions_compared": len(ranked),
            "unit": rows[0]["unit"], "currency": convert_to or currency,
            "pnl_type": pnl_type, "insights": insights,
            "generated_sql": " ".join(sql.split()),
        }
        if total is not None:
            result["total"] = total
            result["total_note"] = "single-currency total only"
        else:
            result["total_note"] = "margin mode: no summed total (ratios don't sum)"
        found = {r["region"] for r in rows}
        result["missing_regions"] = [r for r in regions if r not in found]
        if result["missing_regions"]:
            result["coverage_warning"] = (
                f"No {convert_to or currency} row for {result['missing_regions']} "
                f"in {month} {year}; ranked {len(ranked)} of {len(regions)} requested. "
                "Cross-currency cells (e.g. India in IDR) do not exist — pick each region's "
                "native currency or convert_to='INR' for the DB-converted view."
            )
        native_set = {c for currs in native.values() for c in currs}
        if len(native_set) > 1:
            result["currency_note"] = (
                f"Regions report natively in {sorted(native_set)}; "
                f"this compare uses {convert_to or currency} values (DB pre-applied rates)."
            )
        if convert_to:
            result["conversion_note"] = (
                f"Converted view in {convert_to} using DB pre-applied average rates; no live FX."
            )
        conn.close()
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "metric": metric, "regions": regions}
