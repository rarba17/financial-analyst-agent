"""
Tool 4: Cross-Region Comparison Tool
Purpose: Compare metrics across multiple regions for same period
"""

import sqlite3
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool


@tool
def compare_regions(
    regions: List[str],
    metric: str,
    month: str,
    year: int,
    pnl_type: str = "Reported",
    currency: str = "INR"
) -> Dict[str, Any]:
    """
    Compare a metric across multiple regions for the same time period.
    
    Use this tool when the user asks about:
    - Ranking regions by a metric
    - Comparing performance across regions
    - Which region has the highest/lowest value
    - Regional benchmarking
    
    Examples:
    - "Rank India, Indonesia, and Africa by Net Sales in March 2025"
    - "Compare EBITDA margins across all regions in November 2024"
    - "Which region had the highest EBIT in January 2025?"
    - "Show regional comparison of A&P spend for December 2024"
    
    Args:
        regions: List of region names (e.g., ["India Standalone", "Godrej Indonesia", "Africa"])
        metric: Metric name (e.g., "net_sales_ind_as", "ebitda")
        month: Month name (e.g., "Mar", "Nov")
        year: Year (e.g., 2024, 2025)
        pnl_type: "Reported" or "Organic" (default: "Reported")
        currency: Currency code (default: "INR")
    
    Returns:
        Dictionary containing:
        - ranked_regions: List of regions sorted by metric value
        - total: Sum across all regions
        - shares: Each region's percentage of total
        - gaps: Difference from leader for each region
        - insights: Key observations
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
        region_placeholders = ','.join(['?'] * len(regions))
        
        sql = f"""
        SELECT 
            region,
            {metric} as metric_value,
            unit,
            currency,
            pnl_type
        FROM ftm
        WHERE region IN ({region_placeholders})
            AND month = ?
            AND year = ?
            AND currency = ?
            AND pnl_type = ?
        ORDER BY metric_value DESC
        """
        
        params = regions + [month, year, currency, pnl_type]
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            return {
                "success": False,
                "error": f"No data found for specified regions in {month} {year}"
            }
        
        # Calculate total
        total = sum(row["metric_value"] for row in rows if row["metric_value"] is not None)
        
        # Build ranked results
        ranked_regions = []
        leader_value = rows[0]["metric_value"] if rows else 0
        
        for idx, row in enumerate(rows, 1):
            value = row["metric_value"]
            share = (value / total * 100) if total != 0 else 0
            gap_from_leader = value - leader_value
            
            ranked_regions.append({
                "rank": idx,
                "region": row["region"],
                "value": value,
                "share_of_total": share,
                "gap_from_leader": gap_from_leader,
                "unit": row["unit"],
                "currency": row["currency"]
            })
        
        # Generate insights
        insights = []
        
        if len(ranked_regions) > 0:
            leader = ranked_regions[0]
            insights.append(f"{leader['region']} leads with {leader['share_of_total']:.1f}% share")
        
        if len(ranked_regions) > 1:
            gap_pct = abs(ranked_regions[0]["gap_from_leader"] - ranked_regions[1]["gap_from_leader"]) / ranked_regions[0]["value"] * 100
            insights.append(f"Gap between #1 and #2 is {gap_pct:.1f}%")
        
        result = {
            "success": True,
            "metric": metric,
            "period": f"{month} {year}",
            "ranked_regions": ranked_regions,
            "total": total,
            "unit": rows[0]["unit"] if rows else None,
            "currency": rows[0]["currency"] if rows else None,
            "pnl_type": pnl_type,
            "insights": insights,
            "regions_compared": len(ranked_regions)
        }
        
        conn.close()
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "metric": metric,
            "regions": regions
        }