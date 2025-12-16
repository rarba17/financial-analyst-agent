"""
Tool 5: Driver & Decomposition Analysis Tool
Purpose: Complex waterfall analysis, driver attribution, mix effects
"""

import sqlite3
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool


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
    currency: str = "INR"
) -> Dict[str, Any]:
    """
    Perform complex driver analysis, waterfall decomposition, and mix-effect calculations.
    
    Use this tool when the user asks about:
    - What drove the change in a metric
    - Decompose changes into components
    - Waterfall analysis
    - Attribution of variance
    - Mix and intensity analysis
    - FX impact on margins
    
    Examples:
    - "What are the top drivers of EBITDA change for India?"
    - "Decompose the PBT change into components"
    - "Show waterfall analysis of EBITDA from Oct to Mar"
    - "Mix and A&P intensity analysis for March 2025"
    - "Calculate FX impact on margin for each month"
    
    Args:
        region: Region name or "consolidated" for multi-region analysis
        target_metric: Primary metric to analyze (e.g., "ebitda", "profit_before_tax")
        start_month: Starting month
        start_year: Starting year
        end_month: Ending month
        end_year: Ending year
        analysis_type: Type of analysis:
            - "driver_analysis": Identify top drivers of change
            - "waterfall": Decompose change step-by-step
            - "mix_intensity": Calculate mix effects and intensity metrics
            - "fx_impact": Calculate FX impact on margins
        component_metrics: List of component metrics to analyze (optional)
        pnl_type: "Reported" or "Organic"
        currency: Currency code
    
    Returns:
        Dictionary containing detailed driver analysis and decomposition
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    db_path = os.getenv("DATABASE_PATH", "flattened.db")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if analysis_type == "driver_analysis":
            return _analyze_drivers_core(
                conn, region, target_metric, 
                start_month, start_year, end_month, end_year,
                component_metrics, pnl_type, currency
            )
        
        elif analysis_type == "waterfall":
            return _waterfall_decomposition(
                conn, region, target_metric,
                start_month, start_year, end_month, end_year,
                component_metrics, pnl_type, currency
            )
        
        elif analysis_type == "mix_intensity":
            return _mix_intensity_analysis(
                conn, region, end_month, end_year,
                pnl_type, currency
            )
        
        elif analysis_type == "fx_impact":
            return _fx_impact_analysis(
                conn, region, start_month, start_year,
                end_month, end_year, pnl_type, currency
            )
        
        else:
            return {
                "success": False,
                "error": f"Unknown analysis_type: {analysis_type}"
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "region": region,
            "target_metric": target_metric
        }
    finally:
        if conn:
            conn.close()


def _analyze_drivers_core(
    conn, region, target_metric, 
    start_month, start_year, end_month, end_year,
    component_metrics, pnl_type, currency
) -> Dict[str, Any]:
    """Core driver analysis logic"""
    
    cursor = conn.cursor()
    
    # Default components for EBITDA analysis
    if not component_metrics:
        if target_metric == "ebitda":
            component_metrics = [
                "gross_contribution_gc_of_gsv",
                "total_a_p_spends",
                "fx_gain_loss",
                "other_income_expenses",
                "inter_co_re_charges_income_expenses"
            ]
        elif target_metric == "profit_before_tax":
            component_metrics = [
                "ebitda",
                "depreciation",
                "net_interest_cost",
                "fx_gain_loss",
                "other_income_expenses",
                "inter_co_re_charges_income_expenses",
                "exceptional_income_expense"
            ]
        else:
            component_metrics = []
    
    # Fetch start period data
    sql_start = f"""
    SELECT {target_metric} as target_value,
           {', '.join(component_metrics)}
    FROM ftm
    WHERE region = ? AND month = ? AND year = ?
        AND currency = ? AND pnl_type = ?
    """
    cursor.execute(sql_start, (region, start_month, start_year, currency, pnl_type))
    start_data = cursor.fetchone()
    
    # Fetch end period data
    sql_end = f"""
    SELECT {target_metric} as target_value,
           {', '.join(component_metrics)}
    FROM ftm
    WHERE region = ? AND month = ? AND year = ?
        AND currency = ? AND pnl_type = ?
    """
    cursor.execute(sql_end, (region, end_month, end_year, currency, pnl_type))
    end_data = cursor.fetchone()
    
    if not start_data or not end_data:
        return {
            "success": False,
            "error": "Missing data for start or end period"
        }
    
    # Calculate target metric change
    target_change = end_data["target_value"] - start_data["target_value"]
    target_change_pct = (target_change / start_data["target_value"] * 100) if start_data["target_value"] != 0 else 0
    
    # Calculate component changes
    drivers = []
    for comp in component_metrics:
        start_val = start_data[comp] if start_data[comp] is not None else 0
        end_val = end_data[comp] if end_data[comp] is not None else 0
        change = end_val - start_val
        
        # Calculate contribution to total change
        contribution_pct = (change / abs(target_change) * 100) if target_change != 0 else 0
        
        drivers.append({
            "component": comp.replace('_', ' ').title(),
            "start_value": start_val,
            "end_value": end_val,
            "change": change,
            "contribution_pct": contribution_pct,
            "direction": "positive" if change > 0 else "negative" if change < 0 else "neutral"
        })
    
    # Sort by absolute contribution
    drivers.sort(key=lambda x: abs(x["contribution_pct"]), reverse=True)
    
    result = {
        "success": True,
        "analysis_type": "driver_analysis",
        "target_metric": target_metric,
        "region": region,
        "start_period": f"{start_month} {start_year}",
        "end_period": f"{end_month} {end_year}",
        "target_change": {
            "start_value": start_data["target_value"],
            "end_value": end_data["target_value"],
            "absolute_change": target_change,
            "percentage_change": target_change_pct
        },
        "drivers": drivers,
        "top_3_drivers": drivers[:3]
    }
    
    return result


def _waterfall_decomposition(
    conn, region, target_metric,
    start_month, start_year, end_month, end_year,
    component_metrics, pnl_type, currency
) -> Dict[str, Any]:
    """Waterfall decomposition logic"""
    
    # Similar to driver analysis but formatted as waterfall
    driver_result = _analyze_drivers_core(
        conn, region, target_metric,
        start_month, start_year, end_month, end_year,
        component_metrics, pnl_type, currency
    )
    
    if not driver_result["success"]:
        return driver_result
    
    # Format as waterfall
    waterfall_steps = []
    cumulative = driver_result["target_change"]["start_value"]
    
    for driver in driver_result["drivers"]:
        cumulative += driver["change"]
        waterfall_steps.append({
            "component": driver["component"],
            "impact": driver["change"],
            "cumulative_value": cumulative
        })
    
    result = {
        "success": True,
        "analysis_type": "waterfall",
        "target_metric": target_metric,
        "region": region,
        "start_period": driver_result["start_period"],
        "end_period": driver_result["end_period"],
        "starting_value": driver_result["target_change"]["start_value"],
        "waterfall_steps": waterfall_steps,
        "ending_value": driver_result["target_change"]["end_value"],
        "net_change": driver_result["target_change"]["absolute_change"]
    }
    
    return result


def _mix_intensity_analysis(
    conn, region, month, year, pnl_type, currency
) -> Dict[str, Any]:
    """Mix and intensity analysis for multiple regions"""
    
    cursor = conn.cursor()
    
    # If region is "consolidated", get all regions
    if region.lower() in ["consolidated", "all", "gcpl consolidated"]:
        regions_to_analyze = [
            "India Standalone",
            "Godrej Indonesia",
            "GAUM"  # Add more as needed
        ]
    else:
        regions_to_analyze = [region]
    
    region_placeholders = ','.join(['?'] * len(regions_to_analyze))
    
    sql = f"""
    SELECT 
        region,
        net_sales_ind_as,
        total_a_p_spends,
        ebitda
    FROM ftm
    WHERE region IN ({region_placeholders})
        AND month = ?
        AND year = ?
        AND currency = ?
        AND pnl_type = ?
    """
    
    params = regions_to_analyze + [month, year, currency, pnl_type]
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    if not rows:
        return {
            "success": False,
            "error": "No data found for mix analysis"
        }
    
    # Calculate totals
    total_sales = sum(row["net_sales_ind_as"] for row in rows if row["net_sales_ind_as"])
    total_ap = sum(row["total_a_p_spends"] for row in rows if row["total_a_p_spends"])
    total_ebitda = sum(row["ebitda"] for row in rows if row["ebitda"])
    
    # Calculate for each region
    regional_analysis = []
    for row in rows:
        sales = row["net_sales_ind_as"] or 0
        ap = row["total_a_p_spends"] or 0
        ebitda = row["ebitda"] or 0
        
        mix_pct = (sales / total_sales * 100) if total_sales != 0 else 0
        ap_intensity = (ap / sales * 100) if sales != 0 else 0
        ebitda_margin = (ebitda / sales * 100) if sales != 0 else 0
        
        regional_analysis.append({
            "region": row["region"],
            "net_sales": sales,
            "sales_mix_pct": mix_pct,
            "ap_spend": ap,
            "ap_intensity_pct": ap_intensity,
            "ebitda": ebitda,
            "ebitda_margin_pct": ebitda_margin
        })
    
    # Sort by sales mix
    regional_analysis.sort(key=lambda x: x["sales_mix_pct"], reverse=True)
    
    result = {
        "success": True,
        "analysis_type": "mix_intensity",
        "period": f"{month} {year}",
        "total_sales": total_sales,
        "total_ap": total_ap,
        "total_ebitda": total_ebitda,
        "consolidated_ap_intensity": (total_ap / total_sales * 100) if total_sales != 0 else 0,
        "consolidated_ebitda_margin": (total_ebitda / total_sales * 100) if total_sales != 0 else 0,
        "regional_analysis": regional_analysis
    }
    
    return result


def _fx_impact_analysis(
    conn, region, start_month, start_year, end_month, end_year, pnl_type, currency
) -> Dict[str, Any]:
    """FX impact on margins analysis"""
    
    cursor = conn.cursor()
    
    # Month ordering
    month_order = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    
    # Build month list (simplified - same year assumed)
    start_idx = month_order[start_month]
    end_idx = month_order[end_month]
    months = [m for m, idx in month_order.items() if start_idx <= idx <= end_idx]
    
    month_placeholders = ','.join(['?'] * len(months))
    
    sql = f"""
    SELECT 
        month,
        year,
        operational_ebitda_nsv,
        operational_ebitda_forex_nsv,
        net_sales_ind_as
    FROM ftm
    WHERE region = ?
        AND month IN ({month_placeholders})
        AND year = ?
        AND currency = ?
        AND pnl_type = ?
    ORDER BY 
        CASE month
            WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
            WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
            WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
            WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
        END
    """
    
    params = [region] + months + [start_year, currency, pnl_type]
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    if not rows:
        return {
            "success": False,
            "error": "No data found for FX impact analysis"
        }
    
    # Calculate FX impact for each month
    monthly_fx_impact = []
    fx_impacts = []
    
    for row in rows:
        ebitda_base = row["operational_ebitda_nsv"] or 0
        ebitda_forex = row["operational_ebitda_forex_nsv"] or 0
        
        fx_impact = ebitda_forex - ebitda_base
        fx_impacts.append(fx_impact)
        
        monthly_fx_impact.append({
            "period": f"{row['month']} {row['year']}",
            "ebitda_margin_base": ebitda_base,
            "ebitda_margin_with_fx": ebitda_forex,
            "fx_impact_pp": fx_impact
        })
    
    # Calculate average
    avg_fx_impact = sum(fx_impacts) / len(fx_impacts) if fx_impacts else 0
    
    # Find max impact month
    max_impact_idx = fx_impacts.index(max(fx_impacts, key=abs)) if fx_impacts else 0
    max_impact_month = monthly_fx_impact[max_impact_idx] if monthly_fx_impact else None
    
    result = {
        "success": True,
        "analysis_type": "fx_impact",
        "region": region,
        "period_analyzed": f"{start_month} {start_year} to {end_month} {end_year}",
        "monthly_fx_impact": monthly_fx_impact,
        "average_fx_impact_pp": avg_fx_impact,
        "max_impact_month": max_impact_month
    }
    
    return result