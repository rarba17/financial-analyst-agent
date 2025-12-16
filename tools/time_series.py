"""
Tool 2: Time Series Analysis Tool
Purpose: MoM changes, trends, rolling averages
"""

import sqlite3
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from datetime import datetime


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
    currency: str = "INR"
) -> Dict[str, Any]:
    """
    Analyze metric changes over time with MoM comparisons, trends, and rolling averages.
    Also prints and returns the fully-rendered SQL query string used for execution.
    """
    import os
    from dotenv import load_dotenv

    # --- helpers -------------------------------------------------------------
    def _quote_sql_value(v):
        if v is None:
            return "NULL"
        if isinstance(v, (int, float)):
            # ints/floats printed as-is
            return str(v)
        # strings: single-quote and escape internal single quotes
        s = str(v).replace("'", "''")
        return f"'{s}'"

    def _interpolate_sql(sql: str, params: List[Any]) -> str:
        # Replace '?' one-by-one with quoted param values
        out = sql
        for p in params:
            out = out.replace("?", _quote_sql_value(p), 1)
        return out
    # ------------------------------------------------------------------------

    load_dotenv()
    db_path = os.getenv("DATABASE_PATH", "flattened.db")

    # Month ordering for proper sequencing
    month_order = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Determine which months to fetch
        months_to_fetch: List[tuple] = []
        if start_year == end_year:
            start_idx = month_order[start_month]
            end_idx = month_order[end_month]
            months_to_fetch = [(m, start_year) for m, idx in month_order.items()
                               if start_idx <= idx <= end_idx]
        else:
            # start_year: from start_month..Dec
            start_idx = month_order[start_month]
            months_to_fetch.extend([(m, start_year) for m, idx in month_order.items()
                                    if idx >= start_idx])
            # end_year: from Jan..end_month
            end_idx = month_order[end_month]
            months_to_fetch.extend([(m, end_year) for m, idx in month_order.items()
                                    if idx <= end_idx])

        # Build IN lists & params
        month_list = [m for m, _ in months_to_fetch]
        year_list = sorted(list({y for _, y in months_to_fetch}))  # order not critical for IN

        if not month_list or not year_list:
            return {
                "success": False,
                "error": "Empty month/year selection built from inputs.",
                "generated_sql_query": None,
                "results": [],
                "row_count": 0,
                "metric": metric,
                "region": region
            }

        placeholders = ",".join(["?"] * len(month_list))
        year_placeholders = ",".join(["?"] * len(year_list))

        if pnl_type == "both":
            sql = f"""
            SELECT 
                month,
                year,
                {metric} AS metric_value,
                unit,
                currency,
                pnl_type
            FROM ftm
            WHERE region = ?
              AND month IN ({placeholders})
              AND year IN ({year_placeholders})
              AND currency = ?
              AND pnl_type IN ('Reported', 'Organic')
            ORDER BY pnl_type, year,
              CASE month
                WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
              END
            """
            params: List[Any] = [region] + month_list + year_list + [currency]
        else:
            sql = f"""
            SELECT 
                month,
                year,
                {metric} AS metric_value,
                unit,
                currency,
                pnl_type
            FROM ftm
            WHERE region = ?
              AND month IN ({placeholders})
              AND year IN ({year_placeholders})
              AND currency = ?
              AND pnl_type = ?
            ORDER BY year,
              CASE month
                WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
              END
            """
            params = [region] + month_list + year_list + [currency, pnl_type]

        # Build expanded SQL for logging/return
        expanded_sql = _interpolate_sql(sql, params)

        # Print to terminal (your CLI / server logs)
        print("[analyze_time_series] DB Path:", db_path)
        print("[analyze_time_series] Executing SQL:")
        print(expanded_sql)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Convert raw rows → list of dicts (to expose in "results")
        results = [
            {
                "month": r["month"],
                "year": r["year"],
                "metric_value": r["metric_value"],
                "unit": r["unit"],
                "currency": r["currency"],
                "pnl_type": r["pnl_type"]
            }
            for r in rows
        ]

        # If nothing came back, still return the SQL for debugging
        if not rows:
            return {
                "success": False,
                "error": f"No data found for {region} in the specified period.",
                "generated_sql_query": expanded_sql,
                "sql_params": params,
                "results": [],
                "row_count": 0,
                "metric": metric,
                "region": region
            }

        # Build time-series structures (preserve your existing outputs)
        if pnl_type == "both":
            reported_series: List[Dict[str, Any]] = []
            organic_series: List[Dict[str, Any]] = []
            for row in rows:
                dp = {
                    "month": row["month"],
                    "year": row["year"],
                    "period": f"{row['month']} {row['year']}",
                    "value": row["metric_value"],
                    "unit": row["unit"],
                    "currency": row["currency"]
                }
                if row["pnl_type"] == "Reported":
                    reported_series.append(dp)
                else:
                    organic_series.append(dp)

            result: Dict[str, Any] = {
                "success": True,
                "metric": metric,
                "region": region,
                "reported_time_series": reported_series,
                "organic_time_series": organic_series,
                "unit": rows[0]["unit"],
                "currency": rows[0]["currency"],
            }

            if analysis_type == "mom_change":
                if len(reported_series) >= 2:
                    latest, previous = reported_series[-1], reported_series[-2]
                    abs_chg = latest["value"] - previous["value"]
                    pct_chg = (abs_chg / previous["value"] * 100) if previous["value"] else 0
                    result["reported_mom_change"] = {
                        "from_period": previous["period"],
                        "to_period": latest["period"],
                        "from_value": previous["value"],
                        "to_value": latest["value"],
                        "absolute_change": abs_chg,
                        "percentage_change": pct_chg,
                        "direction": "increase" if abs_chg > 0 else "decrease" if abs_chg < 0 else "flat"
                    }
                if len(organic_series) >= 2:
                    latest, previous = organic_series[-1], organic_series[-2]
                    abs_chg = latest["value"] - previous["value"]
                    pct_chg = (abs_chg / previous["value"] * 100) if previous["value"] else 0
                    result["organic_mom_change"] = {
                        "from_period": previous["period"],
                        "to_period": latest["period"],
                        "from_value": previous["value"],
                        "to_value": latest["value"],
                        "absolute_change": abs_chg,
                        "percentage_change": pct_chg,
                        "direction": "increase" if abs_chg > 0 else "decrease" if abs_chg < 0 else "flat"
                    }

            # Attach SQL + raw rows summary
            result.update({
                "generated_sql_query": expanded_sql,
                "sql_params": params,
                "results": results,
                "row_count": len(results)
            })
            conn.close()
            return result

        # Single pnl_type branch
        time_series: List[Dict[str, Any]] = [
            {
                "month": r["month"],
                "year": r["year"],
                "period": f"{r['month']} {r['year']}",
                "value": r["metric_value"],
                "unit": r["unit"],
                "currency": r["currency"]
            }
            for r in rows
        ]

        result: Dict[str, Any] = {
            "success": True,
            "metric": metric,
            "region": region,
            "time_series": time_series,
            "unit": time_series[0]["unit"] if time_series else None,
            "currency": time_series[0]["currency"] if time_series else None,
            "pnl_type": pnl_type
        }

        # Perform requested analysis
        if analysis_type == "mom_change" and len(time_series) >= 2:
            latest, previous = time_series[-1], time_series[-2]
            abs_chg = latest["value"] - previous["value"]
            pct_chg = (abs_chg / previous["value"] * 100) if previous["value"] else 0
            result["mom_change"] = {
                "from_period": previous["period"],
                "to_period": latest["period"],
                "from_value": previous["value"],
                "to_value": latest["value"],
                "absolute_change": abs_chg,
                "percentage_change": pct_chg,
                "direction": "increase" if abs_chg > 0 else "decrease" if abs_chg < 0 else "flat"
            }

        elif analysis_type == "rolling_avg" and len(time_series) >= 3:
            n = min(3, len(time_series))
            vals = [ts["value"] for ts in time_series[-n:]]
            result["rolling_average"] = {
                "window_size": n,
                "periods_included": [ts["period"] for ts in time_series[-n:]],
                "values": vals,
                "average": sum(vals) / n
            }

        elif analysis_type == "trend" and len(time_series) >= 2:
            first, last = time_series[0]["value"], time_series[-1]["value"]
            total_change = last - first
            total_pct = (total_change / first * 100) if first else 0
            ups = sum(1 for i in range(1, len(time_series)) if time_series[i]["value"] > time_series[i-1]["value"])
            downs = sum(1 for i in range(1, len(time_series)) if time_series[i]["value"] < time_series[i-1]["value"])
            result["trend"] = {
                "direction": "increasing" if ups > downs else "decreasing" if downs > ups else "stable",
                "start_value": first,
                "end_value": last,
                "total_change": total_change,
                "total_change_pct": total_pct,
                "up_months": ups,
                "down_months": downs
            }

        elif analysis_type == "total_change" and len(time_series) >= 2:
            first, last = time_series[0], time_series[-1]
            abs_chg = last["value"] - first["value"]
            pct_chg = (abs_chg / first["value"] * 100) if first["value"] else 0
            result["total_change"] = {
                "start_period": first["period"],
                "end_period": last["period"],
                "start_value": first["value"],
                "end_value": last["value"],
                "absolute_change": abs_chg,
                "percentage_change": pct_chg
            }

        # Attach SQL + raw rows summary
        result.update({
            "generated_sql_query": expanded_sql,
            "sql_params": params,
            "results": results,          # raw table rows
            "row_count": len(results)    # count of raw rows
        })

        conn.close()
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "metric": metric,
            "region": region,
            "generated_sql_query": None,
            "results": [],
            "row_count": 0
        }
