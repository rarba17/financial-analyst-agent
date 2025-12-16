"""
Tool 3: Rankings & Extrema Tool
Purpose: Find peaks, valleys, best/worst months
"""

import sqlite3
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool


@tool
def find_rankings_extrema(
    region: str,
    metric: str,
    months: List[str],
    years: List[int],
    criteria: str = "maximum",
    pnl_type: str = "Reported",
    currency: str = "INR"
) -> Dict[str, Any]:
    """
    Find the peak, valley, or extreme values of a metric across multiple time periods.
    
    Use this tool when the user asks about:
    - Which month had the highest/lowest value
    - Peak or valley identification
    - Best or worst performing month
    - Maximum or minimum values across periods
    
    Examples:
    - "Which month shows the peak EBITDA for India between Oct 2024 and Mar 2025?"
    - "During which month did Indonesia have its lowest BTL spend?"
    - "Find the month with the largest FX Gain for consolidated"
    - "When did Africa achieve its highest Net Sales?"
    
    Args:
        region: Region name (e.g., "India Standalone", "GCPL Consolidated")
        metric: Metric name (e.g., "ebitda", "btl_incl_tpr_ind_as_btl_adj")
        months: List of month names (e.g., ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"])
        years: List of years to include (e.g., [2024, 2025])
        criteria: "maximum" for peak/highest, "minimum" for valley/lowest
        pnl_type: "Reported" or "Organic" (default: "Reported")
        currency: Currency code (default: "INR")
    
    Returns:
        Dictionary containing:
        - peak/valley month and value
        - all months ranked
        - context (previous peak, improvement, etc.)
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    db_path = os.getenv("DATABASE_PATH", "flattened.db")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build query
        month_placeholders = ','.join(['?'] * len(months))
        year_placeholders = ','.join(['?'] * len(years))
        
        order_direction = "DESC" if criteria == "maximum" else "ASC"
        
        sql = f"""
        SELECT 
            month,
            year,
            {metric} as metric_value,
            unit,
            currency,
            pnl_type
        FROM ftm
        WHERE region = ?
            AND month IN ({month_placeholders})
            AND year IN ({year_placeholders})
            AND currency = ?
            AND pnl_type = ?
        ORDER BY 
            metric_value {order_direction},
            year DESC,
            CASE month
                WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
            END DESC
        """
        
        params = [region] + months + years + [currency, pnl_type]
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            return {
                "success": False,
                "error": f"No data found for {region} in specified periods"
            }
        
        # Get extreme value (first row after ordering)
        extreme = rows[0]
        extreme_result = {
            "month": extreme["month"],
            "year": extreme["year"],
            "period": f"{extreme['month']} {extreme['year']}",
            "value": extreme["metric_value"],
            "unit": extreme["unit"],
            "currency": extreme["currency"]
        }
        
        # Get all values ranked
        all_rankings = []
        for idx, row in enumerate(rows, 1):
            all_rankings.append({
                "rank": idx,
                "month": row["month"],
                "year": row["year"],
                "period": f"{row['month']} {row['year']}",
                "value": row["metric_value"]
            })
        
        # Calculate context
        context = {}
        if len(rows) >= 2:
            second_best = rows[1]
            improvement = extreme["metric_value"] - second_best["metric_value"]
            improvement_pct = (improvement / second_best["metric_value"] * 100) if second_best["metric_value"] != 0 else 0
            
            context = {
                "second_best_period": f"{second_best['month']} {second_best['year']}",
                "second_best_value": second_best["metric_value"],
                "improvement": improvement,
                "improvement_pct": improvement_pct
            }
        
        result = {
            "success": True,
            "metric": metric,
            "region": region,
            "criteria": criteria,
            "extreme": extreme_result,
            "all_rankings": all_rankings,
            "context": context,
            "pnl_type": pnl_type,
            "total_periods_analyzed": len(rows)
        }
        
        conn.close()
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "metric": metric,
            "region": region
        }