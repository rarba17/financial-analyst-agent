"""
Tool 5: Driver & Decomposition (Phase 1 rework per a.md P1.5)
- Generic component inference from FINANCIAL_HIERARCHY (not EBITDA/PBT-only)
- N-region mix (accepts regions list; 'consolidated' expands to caller list)
- Cross-year FX (explicit (month,year) list like time_series)
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

try:
    from tools._helpers import MONTH_ORDER, infer_components, normalize_month
except ImportError:  # pragma: no cover
    from _helpers import MONTH_ORDER, infer_components, normalize_month  # type: ignore


def _db_path() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("DATABASE_PATH", "flattened.db")


def _period_pairs(sm: str, sy: int, em: str, ey: int) -> List[tuple]:
    sm, em = normalize_month(sm), normalize_month(em)
    ordered = sorted(MONTH_ORDER, key=MONTH_ORDER.get)
    if sy == ey:
        return [(m, sy) for m in ordered if MONTH_ORDER[sm] <= MONTH_ORDER[m] <= MONTH_ORDER[em]]
    out = [(m, sy) for m in ordered if MONTH_ORDER[m] >= MONTH_ORDER[sm]]
    for y in range(sy + 1, ey):
        out += [(m, y) for m in ordered]
    return out + [(m, ey) for m in ordered if MONTH_ORDER[m] <= MONTH_ORDER[em]]


@tool
def analyze_drivers(
    region: str,
    target_metric: str,
    start_month: str,
    start_year: int,
    end_month: str,
    end_year: int,
    analysis_type: str = "driver_analysis",
    component_metrics: Optional[List[str]] = None,
    pnl_type: str = "Reported",
    currency: str = "INR",
    regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Driver attribution, waterfall, mix/intensity, FX impact.

    Args:
        region: Region (or 'consolidated'/'all' with `regions` list for mix)
        target_metric: Metric under analysis (any P&L line; components inferred)
        start_month/start_year/end_month/end_year: Window
        analysis_type: driver_analysis | waterfall | mix_intensity | fx_impact
        component_metrics: Override inferred components
        pnl_type/currency: Filters
        regions: N-region list for mix_intensity (replaces hardcoded 3)
    """
    db_path = _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if analysis_type in ("driver_analysis", "waterfall"):
            comps = component_metrics or infer_components(target_metric)
            if not comps:
                return {"success": False, "error": f"No components for {target_metric}"}
            cols = [target_metric] + [c for c in comps if c != target_metric]
            sel = ", ".join([f'"{c}"' for c in cols])
            cur = conn.cursor()
            cur.execute(
                f'SELECT {target_metric} AS target_value, {sel} FROM ftm WHERE region=? '
                'AND month=? AND year=? AND currency=? AND pnl_type=?',
                (region, normalize_month(start_month), start_year, currency, pnl_type),
            )
            s = cur.fetchone()
            cur.execute(
                f'SELECT {target_metric} AS target_value, {sel} FROM ftm WHERE region=? '
                'AND month=? AND year=? AND currency=? AND pnl_type=?',
                (region, normalize_month(end_month), end_year, currency, pnl_type),
            )
            e = cur.fetchone()
            if not s or not e:
                return {"success": False, "error": "Missing start/end data"}
            chg = (e["target_value"] or 0) - (s["target_value"] or 0)
            drivers = []
            for c in comps:
                sv = s[c] if s[c] is not None else 0
                ev = e[c] if e[c] is not None else 0
                d = ev - sv
                drivers.append({"component": c.replace("_", " ").title(),
                                "metric": c, "start_value": sv, "end_value": ev,
                                "change": d,
                                "contribution_pct": (d / abs(chg) * 100) if chg else 0,
                                "direction": "positive" if d > 0 else "negative" if d < 0 else "neutral"})
            drivers.sort(key=lambda x: abs(x["contribution_pct"]), reverse=True)
            base = {"success": True, "analysis_type": analysis_type,
                    "target_metric": target_metric, "region": region,
                    "start_period": f"{start_month} {start_year}",
                    "end_period": f"{end_month} {end_year}",
                    "target_change": {"start_value": s["target_value"],
                                      "end_value": e["target_value"],
                                      "absolute_change": chg,
                                      "percentage_change": (chg / s["target_value"] * 100) if s["target_value"] else 0},
                    "drivers": drivers, "top_3_drivers": drivers[:3],
                    "components_inferred": component_metrics is None}
            if analysis_type == "waterfall":
                cum, steps = s["target_value"] or 0, []
                for d in drivers:
                    cum += d["change"]
                    steps.append({"component": d["component"], "impact": d["change"],
                                  "cumulative_value": cum})
                base = {"success": True, "analysis_type": "waterfall",
                        "target_metric": target_metric, "region": region,
                        "start_period": base["start_period"], "end_period": base["end_period"],
                        "starting_value": s["target_value"], "waterfall_steps": steps,
                        "ending_value": e["target_value"], "net_change": chg}
            return base

        if analysis_type == "mix_intensity":
            cur = conn.cursor()
            if regions:
                rlist = regions
            elif region.lower() in ("consolidated", "all", "gcpl consolidated"):
                # caller must pass explicit list now; default keeps old 3 for compat
                rlist = ["India Standalone", "Godrej Indonesia", "GAUM"]
            else:
                rlist = [region]
            rph = ",".join(["?"] * len(rlist))
            cur.execute(
                f"""SELECT region, net_sales_ind_as, total_a_p_spends, ebitda FROM ftm
                    WHERE region IN ({rph}) AND month=? AND year=? AND currency=? AND pnl_type=?""",
                rlist + [normalize_month(end_month), end_year, currency, pnl_type],
            )
            rows = cur.fetchall()
            if not rows:
                return {"success": False, "error": "No data for mix analysis"}
            ts = sum(r["net_sales_ind_as"] or 0 for r in rows)
            ta = sum(r["total_a_p_spends"] or 0 for r in rows)
            te = sum(r["ebitda"] or 0 for r in rows)
            reg = []
            for r in rows:
                s_ = r["net_sales_ind_as"] or 0
                reg.append({"region": r["region"], "net_sales": s_,
                            "sales_mix_pct": (s_ / ts * 100) if ts else 0,
                            "ap_spend": r["total_a_p_spends"] or 0,
                            "ap_intensity_pct": ((r["total_a_p_spends"] or 0) / s_ * 100) if s_ else 0,
                            "ebitda": r["ebitda"] or 0,
                            "ebitda_margin_pct": ((r["ebitda"] or 0) / s_ * 100) if s_ else 0})
            reg.sort(key=lambda x: x["sales_mix_pct"], reverse=True)
            return {"success": True, "analysis_type": "mix_intensity",
                    "period": f"{end_month} {end_year}", "total_sales": ts,
                    "total_ap": ta, "total_ebitda": te,
                    "consolidated_ap_intensity": (ta / ts * 100) if ts else 0,
                    "consolidated_ebitda_margin": (te / ts * 100) if ts else 0,
                    "regional_analysis": reg, "regions_analyzed": len(reg)}

        if analysis_type == "fx_impact":
            cur = conn.cursor()
            pairs = _period_pairs(start_month, start_year, end_month, end_year)
            cond = " OR ".join(["(month=? AND year=?)"] * len(pairs))
            flat: List[Any] = []
            for m, y in pairs:
                flat += [m, y]
            cur.execute(
                f"""SELECT month, year, operational_ebitda_nsv, operational_ebitda_forex_nsv,
                    net_sales_ind_as FROM ftm WHERE region=? AND ({cond})
                    AND currency=? AND pnl_type=?
                    ORDER BY year, CASE month WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                    WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                    WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                    WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12 END""",
                [region] + flat + [currency, pnl_type],
            )
            rows = cur.fetchall()
            if not rows:
                return {"success": False, "error": "No data for FX analysis"}
            monthly, impacts = [], []
            for r in rows:
                fx = (r["operational_ebitda_forex_nsv"] or 0) - (r["operational_ebitda_nsv"] or 0)
                impacts.append(fx)
                monthly.append({"period": f"{r['month']} {r['year']}",
                                "ebitda_margin_base": r["operational_ebitda_nsv"],
                                "ebitda_margin_with_fx": r["operational_ebitda_forex_nsv"],
                                "fx_impact_pp": fx})
            idx = max(range(len(impacts)), key=lambda i: abs(impacts[i])) if impacts else 0
            return {"success": True, "analysis_type": "fx_impact", "region": region,
                    "period_analyzed": f"{start_month} {start_year} to {end_month} {end_year}",
                    "monthly_fx_impact": monthly,
                    "average_fx_impact_pp": sum(impacts) / len(impacts) if impacts else 0,
                    "max_impact_month": monthly[idx] if monthly else None,
                    "cross_year": start_year != end_year}
        return {"success": False, "error": f"Unknown analysis_type: {analysis_type}"}
    except Exception as e:
        return {"success": False, "error": str(e), "region": region,
                "target_metric": target_metric}
    finally:
        conn.close()
