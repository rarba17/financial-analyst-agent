"""
Tool 1: Basic Metrics Tool
Purpose: Fast single-value retrieval for point-in-time metrics
"""

import sqlite3
from typing import Dict, Any, Optional
from langchain_core.tools import tool


@tool
def query_basic_metrics(
    region: str,
    metric: str,
    month: str,
    year: int,
    pnl_type: str = "both",
    currency: str = "auto"
) -> Dict[str, Any]:
    """
    Retrieve a single metric value for a specific period and region.
    
    Use this tool when the user asks for a simple, single metric value for one specific time period.
    
    Examples of when to use this tool:
    - "What was India's Net Sales in December 2024?"
    - "Show consolidated EBITDA for March 2025"
    - "What was Indonesia's COGS in February 2025?"
    - "Give me the Gross Sales for Africa in October 2024"
    
    Args:
        region: Region name (e.g., "India Standalone", "GCPL Consolidated", "Indonesia")
        metric: Metric name from database (e.g., "net_sales_ind_as", "ebitda", "gross_sales")
        month: Month name (e.g., "Dec", "Mar", "Oct")
        year: Year as integer (e.g., 2024, 2025)
        pnl_type: "Reported", "Organic", or "both" (default: "both" - returns both types)
        currency: Currency code or "auto" to detect local currency (default: "auto")
    
    Returns:
        Dictionary containing metric values for both Reported and Organic P&L types
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    db_path = os.getenv("DATABASE_PATH", "flattened.db")
    
    # Region to Local Currency mapping
    REGION_CURRENCY_MAP = {
        "Godrej Indonesia": "IDR",
        "Indonesia": "IDR",
        "India Standalone": "INR",
        "GCPL India Cluster": "INR",
        "GCPL Consolidated": "INR",
        "Bangladesh": "BDT",
        "Sri Lanka": "LKR",
        "GAUM": "USD",
        "Nigeria": "NGN",
        "Ghana": "GHS",
        "Kenya": "KES",
        "Kenya LC": "KES",
        "Tanzania": "TZS",
        "Zambia": "ZMW",
        "Argentina": "ARS",
        "Chile": "CLP",
        "LATAM": "USD",
    }
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Auto-detect currency if set to "auto"
        if currency == "auto":
            # Try to match region to local currency
            detected_currency = None
            for region_key, curr in REGION_CURRENCY_MAP.items():
                if region_key.lower() in region.lower():
                    detected_currency = curr
                    break
            
            # If no match, query the database to find available currency
            if not detected_currency:
                cursor.execute("""
                    SELECT DISTINCT currency 
                    FROM ftm 
                    WHERE region = ? AND month = ? AND year = ?
                    LIMIT 1
                """, (region, month, year))
                row = cursor.fetchone()
                detected_currency = row["currency"] if row else "INR"
            
            currency = detected_currency
        
        # Fetch both Reported and Organic
        if pnl_type == "both":
            sql = f"""
            SELECT 
                region,
                {metric} as metric_value,
                unit,
                currency,
                pnl_type,
                month,
                year
            FROM ftm
            WHERE region = ?
                AND month = ?
                AND year = ?
                AND currency = ?
                AND pnl_type IN ('Reported', 'Organic')
            ORDER BY pnl_type DESC
            """
            
            cursor.execute(sql, (region, month, year, currency))
            rows = cursor.fetchall()
            
            if not rows:
                return {
                    "success": False,
                    "error": f"No data found for {region} in {month} {year} with currency {currency}",
                    "metric": metric,
                    "region": region,
                    "period": f"{month} {year}",
                    "currency_used": currency
                }
            
            # Organize by pnl_type
            reported_value = None
            organic_value = None
            unit = rows[0]["unit"]
            
            for row in rows:
                if row["pnl_type"] == "Reported":
                    reported_value = row["metric_value"]
                elif row["pnl_type"] == "Organic":
                    organic_value = row["metric_value"]
            
            result = {
                "success": True,
                "metric": metric,
                "reported_value": reported_value,
                "organic_value": organic_value,
                "unit": unit,
                "currency": currency,
                "region": region,
                "period": f"{month} {year}",
                "generated_sql": sql
            }
        
        else:
            # Fetch specific pnl_type
            sql = f"""
            SELECT 
                region,
                {metric} as metric_value,
                unit,
                currency,
                pnl_type,
                month,
                year
            FROM ftm
            WHERE region = ?
                AND month = ?
                AND year = ?
                AND currency = ?
                AND pnl_type = ?
            LIMIT 1
            """
            
            cursor.execute(sql, (region, month, year, currency, pnl_type))
            row = cursor.fetchone()
            
            if not row:
                return {
                    "success": False,
                    "error": f"No data found for {region} in {month} {year}",
                    "metric": metric,
                    "region": region,
                    "period": f"{month} {year}",
                    "currency_used": currency
                }
            
            result = {
                "success": True,
                "metric": metric,
                "value": row["metric_value"],
                "unit": row["unit"],
                "currency": row["currency"],
                "region": row["region"],
                "period": f"{row['month']} {row['year']}",
                "pnl_type": row["pnl_type"],
                "generated_sql": sql
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


# Helper function to format the output for the agent
def format_basic_metric_output(result: Dict[str, Any]) -> str:
    """Format the basic metric result into a readable string"""
    if not result.get("success"):
        return f"❌ Error: {result.get('error')}"
    
    value = result["value"]
    unit = result["unit"]
    currency = result["currency"]
    
    # Format the value based on unit
    if unit == "Crore":
        if value < 1:
            formatted_value = f"₹{value * 100:.1f} L"
        else:
            formatted_value = f"₹{value:.1f} Cr"
    else:
        formatted_value = f"{currency} {value} {unit}"
    
    output = f"""
**{result['metric'].replace('_', ' ').title()}** - {result['region']}
- **Period**: {result['period']}
- **Value**: {formatted_value}
- **Type**: {result['pnl_type']}
"""
    
    return output.strip()