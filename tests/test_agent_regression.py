"""
Regression bank for the CCPL financial agent (a.md Sections 6 + 7).

Tags mirror a.md: works_now (ftm-only) vs phase1/phase2 (new tools).
All tests invoke tools directly (no LLM) and assert success + valid payload.
DB truth: Data Files/distincts.json. Verified cells are commented with values.

Run:  DATABASE_PATH="Data Files/flattened.db" pytest tests/ -q
"""

import os

import pytest

os.environ.setdefault("DATABASE_PATH", "Data Files/flattened.db")

from tools.annual import query_fy_half  # noqa: E402
from tools.basic_metrics import query_basic_metrics  # noqa: E402
from tools.budget_actual import query_budget_variance  # noqa: E402
from tools.cumulative import query_qtd_ytd  # noqa: E402
from tools.driver_analysis import analyze_drivers  # noqa: E402
from tools.growth import query_yoy_growth  # noqa: E402
from tools.margins import query_margin  # noqa: E402
from tools.region_comparison import compare_regions  # noqa: E402
from tools.rankings_extrema import find_rankings_extrema  # noqa: E402
from tools.time_series import analyze_time_series  # noqa: E402


def call(tool, args):
    res = tool.invoke(args)
    assert isinstance(res, dict)
    return res


# ---------- A. Single-value lookups [WORKS NOW] ----------


def test_a01_india_nsv_dec24():
    # verified: 826.0 Crore, Reported, INR
    r = call(query_basic_metrics, {"region": "India Standalone", "metric": "net_sales_ind_as",
                                   "month": "Dec", "year": 2024, "pnl_type": "Reported", "currency": "INR"})
    assert r["success"] and r["reported_value"] == pytest.approx(826.0)


def test_a02_wide_fetch_siblings_one_call():
    # Total + Domestic + Exports in ONE sql call (Phase 1)
    r = call(query_basic_metrics, {"region": "India Standalone", "metric": "gross_sales",
                                   "metrics": ["gross_domestic_sales", "gross_export_sales"],
                                   "month": "Dec", "year": 2024, "pnl_type": "Reported", "currency": "INR"})
    assert r["success"] and set(r["metrics"]) >= {"gross_sales", "gross_domestic_sales", "gross_export_sales"}


def test_a03_alias_region_indonesia():
    r = call(query_basic_metrics, {"region": "Indonesia", "metric": "net_sales_ind_as",
                                   "month": "Nov", "year": 2024, "pnl_type": "Reported", "currency": "IDR"})
    assert r["success"]


def test_a04_bangladesh_taka():
    r = call(query_basic_metrics, {"region": "Bangladesh", "metric": "cost_of_goods_sold",
                                   "month": "Oct", "year": 2024, "pnl_type": "Reported", "currency": "Taka"})
    assert r["success"]


# ---------- B. Margins [phase2 margins tool] ----------


def test_b01_ebitda_margin_legs():
    # verified: EBITDA 266.0 / NSV 826.0 = 32.2%
    r = call(query_margin, {"numerator": "ebitda", "denominator": "net_sales_ind_as",
                            "region": "India Standalone", "month": "Dec", "year": 2024})
    assert r["success"]
    row = r["rows"][0]
    assert row["numerator"] == pytest.approx(266.0)
    assert row["denominator"] == pytest.approx(826.0)
    assert row["margin_pct"] == pytest.approx(32.2, abs=0.1)


# ---------- C. Time-series [WORKS NOW + yoy_sply] ----------


def test_c01_mom_change():
    r = call(analyze_time_series, {"region": "India Standalone", "metric": "ebitda",
                                   "start_month": "Feb", "start_year": 2025, "end_month": "Mar",
                                   "end_year": 2025, "analysis_type": "mom_change"})
    assert r["success"] and "mom_change" in r


def test_c02_yoy_sply_dec24():
    # verified: Dec24 826.0 vs Dec23 782.0 -> +5.63%
    r = call(analyze_time_series, {"region": "India Standalone", "metric": "net_sales_ind_as",
                                   "start_month": "Dec", "start_year": 2024, "end_month": "Dec",
                                   "end_year": 2024, "analysis_type": "yoy_sply"})
    assert r["success"] and r["yoy_sply"]["yoy_pct"] == pytest.approx(5.63, abs=0.05)


def test_c03_sply_always_attached():
    r = call(analyze_time_series, {"region": "India Standalone", "metric": "ebitda",
                                   "start_month": "Oct", "start_year": 2024, "end_month": "Dec",
                                   "end_year": 2024, "analysis_type": "trend"})
    assert r["success"] and "sply_comparison" in r


# ---------- D. Rankings [WORKS NOW, null-safe] ----------


def test_d01_peak_month():
    r = call(find_rankings_extrema, {"region": "India Standalone", "metric": "ebitda",
                                     "months": ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
                                     "years": [2024, 2025], "criteria": "maximum"})
    assert r["success"] and r["extreme"]["value"] is not None
    assert r["total_periods_analyzed"] >= 5


def test_d02_margin_expression_rank():
    r = call(find_rankings_extrema, {"region": "India Standalone", "metric": "ebitda/net_sales_ind_as",
                                     "months": ["Oct", "Nov", "Dec"], "years": [2024],
                                     "criteria": "maximum"})
    assert r["success"]


# ---------- E. Cross-region [WORKS NOW + guard] ----------


def test_e01_same_currency_rank():
    r = call(compare_regions, {"regions": ["India Standalone", "Godrej Indonesia", "GAUM"],
                               "metric": "net_sales_ind_as", "month": "Mar", "year": 2025,
                               "currency": "INR"})
    assert r["success"] and r["regions_compared"] == 3
    assert "single-currency" in r["total_note"]


def test_e02_mixed_currency_flagged():
    # India has no IDR row: tool must surface missing_regions, never silently sum
    r = compare_regions.invoke({"regions": ["India Standalone", "Godrej Indonesia"],
                                "metric": "net_sales_ind_as", "month": "Mar", "year": 2025,
                                "currency": "IDR"})
    assert r["success"] is True
    assert "India Standalone" in r["missing_regions"]
    assert "coverage_warning" in r


def test_e03_margin_mode():
    r = call(compare_regions, {"regions": ["India Standalone", "Godrej Indonesia", "GAUM"],
                               "metric": "ebitda", "metric_b": "net_sales_ind_as",
                               "month": "Mar", "year": 2025, "currency": "INR"})
    assert r["success"] and r["margin_mode"]


# ---------- F. Drivers [WORKS NOW + generic] ----------


def test_f01_ebitda_drivers():
    r = call(analyze_drivers, {"region": "India Standalone", "target_metric": "ebitda",
                               "start_month": "Oct", "start_year": 2024, "end_month": "Mar",
                               "end_year": 2025, "analysis_type": "driver_analysis"})
    assert r["success"] and len(r["top_3_drivers"]) == 3


def test_f02_pat_generic_components():
    # Phase 1: non-EBITDA/PBT targets now decompose via hierarchy
    r = call(analyze_drivers, {"region": "India Standalone", "target_metric": "profit_after_tax",
                               "start_month": "Dec", "start_year": 2024, "end_month": "Mar",
                               "end_year": 2025, "analysis_type": "driver_analysis"})
    assert r["success"] and len(r["drivers"]) >= 2


def test_f03_cross_year_fx():
    r = call(analyze_drivers, {"region": "India Standalone", "target_metric": "ebitda",
                               "start_month": "Oct", "start_year": 2024, "end_month": "Mar",
                               "end_year": 2025, "analysis_type": "fx_impact"})
    assert r["success"] and r["cross_year"] is True


def test_f04_n_region_mix():
    r = call(analyze_drivers, {"region": "all", "target_metric": "ebitda",
                               "start_month": "Mar", "start_year": 2025, "end_month": "Mar",
                               "end_year": 2025, "analysis_type": "mix_intensity",
                               "regions": ["India Standalone", "Godrej Indonesia", "GAUM",
                                           "Bangladesh", "Nigeria"]})
    assert r["success"] and r["regions_analyzed"] == 5


# ---------- G. YoY / growth [PHASE 2] ----------


def test_g01_ftm_yoy_computed():
    r = call(query_yoy_growth, {"table": "ftm", "region": "India Standalone",
                                "metric": "net_sales_ind_as", "month": "Dec", "year": 2024})
    assert r["success"] and r["computed_sply"]["yoy_pct"] == pytest.approx(5.63, abs=0.05)


# ---------- H. QTD/YTD [PHASE 2] ----------


def test_h01_qtd_val():
    # verified: QTD NSV Dec 2024 India = 2160.0
    r = call(query_qtd_ytd, {"table": "qtd", "region": "India Standalone",
                             "metric": "net_sales_ind_as", "month": "Dec", "year": 2024,
                             "lens": "val"})
    assert r["success"] and r["values"]["net_sales_ind_as"] == pytest.approx(2160.0)


def test_h02_ytd_aop_lens():
    r = call(query_qtd_ytd, {"table": "ytd", "region": "India Standalone",
                             "metric": "net_sales_ind_as", "month": "Dec", "year": 2024,
                             "lens": "aop"})
    assert r["success"]


# ---------- I. Budget [PHASE 2] ----------


def test_i01_quarter_budget_only():
    # verified: Q3 2024 India budget NSV = 2296.0, actual must be None + disclaimer
    r = call(query_budget_variance, {"table": "quarter", "region": "India Standalone",
                                     "metric": "net_sales_ind_as", "quarter": "Q3", "year": 2024})
    assert r["success"] and r["budget"] == pytest.approx(2296.0)
    assert r["actual"] is None and "budget-only" in r["disclaimer"]


# ---------- J/K. FY/Half [PHASE 2] ----------


def test_k01_fy_val():
    # verified: FY2024 GCPL India Cluster NSV = 8417.0 (no India Standalone in fy)
    r = call(query_fy_half, {"table": "fy", "region": "GCPL India Cluster",
                             "metric": "net_sales_ind_as", "year": 2024, "lens": "val"})
    assert r["success"] and r["values"]["net_sales_ind_as"] == pytest.approx(8417.0)


def test_k02_half_index_only():
    r = call(query_fy_half, {"table": "half", "region": "GCPL Consolidated",
                             "metric": "net_sales_ind_as", "year": 2025, "half": "both"})
    assert r["success"] and "index only" in r["disclaimer"]


# ---------- N. Out-of-scope contract ----------


def test_n01_missing_period_no_rows():
    r = call(query_basic_metrics, {"region": "India Standalone", "metric": "net_sales_ind_as",
                                   "month": "Jul", "year": 2024, "pnl_type": "Reported", "currency": "INR"})
    assert r["success"] is False  # Apr-Sep never hallucinated
