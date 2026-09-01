"""
Phase 5 Test Suite – SIF-Insight
=================================
Tests cover:
  • KPI calculations
  • SIF percentage accuracy
  • Barrier failure counts and Pareto cumulative %
  • LSR counts
  • Site density
  • Hazard aggregation
  • Date filtering (filter_analytics_df)
  • Keyword filtering (filter_analytics_df)
  • CSV export (export_to_csv)
  • Empty / small dataset handling
"""

import io
from datetime import datetime, timedelta, date
import os
import pandas as pd
import pytest

# Redirect database path to isolated test file prior to database module imports
import database.db
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_db.sqlite")
database.db.DB_PATH = TEST_DB_PATH

from database.db import (
    get_connection, init_db, save_report, save_ai_prediction,
    save_hse_review, update_report_status, get_all_reports
)

from services.analytics import (
    calculate_kpi_metrics,
    export_to_csv,
    filter_analytics_df,
    generate_management_insights,
    get_barrier_pareto_data,
    get_hazard_energy_analysis_data,
    get_lsr_analysis_data,
    get_risk_heatmap_data,
    get_sif_distribution_data,
    get_sif_trend_data,
    get_site_safety_intelligence_data,
)


# ===========================================================================
# Shared Fixtures
# ===========================================================================


@pytest.fixture
def empty_dataset():
    """Returns an empty DataFrame representing no reports."""
    cols = [
        "id", "created_at", "report_type", "site", "location", "original_text",
        "translated_text", "report_status", "immediate_danger", "review_priority",
        "resolved_sif_label", "resolved_priority", "resolved_activity",
        "resolved_hazard", "resolved_energy_source", "resolved_exposure",
        "resolved_failed_barrier", "resolved_potential_consequence",
        "resolved_life_saving_rules", "ai_confidence", "classifier_mode",
        "model_version", "ai_sif_score", "evidence_phrases",
    ]
    return pd.DataFrame(columns=cols)


@pytest.fixture
def mock_dataset():
    """Returns a mock DataFrame for testing analytics calculations."""
    base_time = datetime(2026, 8, 15, 10, 0, 0)

    data = [
        # Report 1 – SIF-potential, failed barrier, 10 days ago
        {
            "id": 1,
            "created_at": (base_time - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": "Near Miss",
            "site": "Site Alpha",
            "location": "Rig 1",
            "original_text": "LOTO was not verified on electrical panel.",
            "translated_text": None,
            "report_status": "Accepted",
            "immediate_danger": 0,
            "review_priority": "High",
            "resolved_sif_label": "SIF-potential",
            "resolved_priority": "High",
            "resolved_activity": "Electrical maintenance",
            "resolved_hazard": "Electrical shock",
            "resolved_energy_source": "Electrical",
            "resolved_exposure": "Technician exposed",
            "resolved_failed_barrier": "LOTO Verification",
            "resolved_potential_consequence": "Electrocution",
            "resolved_life_saving_rules": ["Energy Isolation", "Bypassing Safety Controls"],
            "ai_confidence": 0.92,
            "classifier_mode": "hybrid",
            "model_version": "v1.0",
            "ai_sif_score": 8,
            "evidence_phrases": ["not verified", "LOTO"],
        },
        # Report 2 – Non-SIF, no failed barrier, 5 days ago
        {
            "id": 2,
            "created_at": (base_time - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": "Unsafe Condition",
            "site": "Site Alpha",
            "location": "Yard",
            "original_text": "Slip hazard due to water puddle.",
            "translated_text": None,
            "report_status": "Pending HSE Review",
            "immediate_danger": 0,
            "review_priority": "Low",
            "resolved_sif_label": "Non-SIF-potential",
            "resolved_priority": "Low",
            "resolved_activity": "Walking",
            "resolved_hazard": "Water puddle",
            "resolved_energy_source": "None",
            "resolved_exposure": "General workers",
            "resolved_failed_barrier": "None",
            "resolved_potential_consequence": "Minor slip",
            "resolved_life_saving_rules": [],
            "ai_confidence": 0.85,
            "classifier_mode": "ml_model",
            "model_version": "v1.0",
            "ai_sif_score": 3,
            "evidence_phrases": [],
        },
        # Report 3 – SIF-potential, immediate danger, critical, today
        {
            "id": 3,
            "created_at": base_time.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": "Incident",
            "site": "Site Beta",
            "location": "Warehouse",
            "original_text": "Worker under suspended load in lifting zone.",
            "translated_text": "Worker stood beneath crane.",
            "report_status": "Action Assigned",
            "immediate_danger": 1,
            "review_priority": "Critical",
            "resolved_sif_label": "SIF-potential",
            "resolved_priority": "Critical",
            "resolved_activity": "Lifting operation",
            "resolved_hazard": "Suspended load",
            "resolved_energy_source": "Gravity",
            "resolved_exposure": "Rigger",
            "resolved_failed_barrier": "Safe Zone Clearance",
            "resolved_potential_consequence": "Crushing",
            "resolved_life_saving_rules": ["Line of Fire", "Safe Mechanical Lifting"],
            "ai_confidence": 0.88,
            "classifier_mode": "hybrid",
            "model_version": "v1.0",
            "ai_sif_score": 9,
            "evidence_phrases": ["suspended load", "lifting zone"],
        },
    ]
    return pd.DataFrame(data)


# ===========================================================================
# 1. Empty-dataset handling
# ===========================================================================


def test_empty_dataset_handling(empty_dataset):
    kpi = calculate_kpi_metrics(empty_dataset)
    assert kpi["total_reports"] == 0
    assert kpi["sif_precursor_pct"] == 0.0

    assert get_sif_trend_data(empty_dataset).empty
    assert get_sif_distribution_data(empty_dataset).empty
    assert get_barrier_pareto_data(empty_dataset).empty
    assert get_lsr_analysis_data(empty_dataset).empty
    assert get_site_safety_intelligence_data(empty_dataset).empty

    insights = generate_management_insights(empty_dataset)
    assert len(insights) == 1
    assert "no" in insights[0].lower() or "insufficient" in insights[0].lower() or "not" in insights[0].lower()


# ===========================================================================
# 2. KPI metrics calculation
# ===========================================================================


def test_kpi_metrics_calculation(mock_dataset):
    kpi = calculate_kpi_metrics(mock_dataset)

    assert kpi["total_reports"] == 3
    # 2 of 3 are SIF-potential → 66.7 %
    assert kpi["sif_precursor_pct"] == 66.7
    # High (report 1) + Critical (report 3)
    assert kpi["critical_high_count"] == 2
    # report 2 is Pending HSE Review
    assert kpi["open_reviews_count"] == 1
    # report 3 has immediate_danger = 1
    assert kpi["immediate_danger_count"] == 1
    # LOTO + Safe Zone = 2 barrier failures / 3 = 66.7 %
    assert kpi["barrier_failure_rate"] == 66.7


# ===========================================================================
# 3. SIF % accuracy (same as kpi_metrics but isolated)
# ===========================================================================


def test_sif_percentage_accuracy(mock_dataset):
    kpi = calculate_kpi_metrics(mock_dataset)
    expected = round(2 / 3 * 100, 1)
    assert kpi["sif_precursor_pct"] == expected


# ===========================================================================
# 4. SIF trend aggregation
# ===========================================================================


def test_sif_trend_aggregation(mock_dataset):
    trend_df = get_sif_trend_data(mock_dataset, freq="W")
    assert not trend_df.empty
    assert "Period" in trend_df.columns
    assert "Total" in trend_df.columns
    assert "SIF-potential" in trend_df.columns


# ===========================================================================
# 5. SIF risk distribution
# ===========================================================================


def test_sif_distribution(mock_dataset):
    dist_df = get_sif_distribution_data(mock_dataset)
    assert len(dist_df) == 2
    assert set(dist_df["SIF Label"]) == {"SIF-potential", "Non-SIF-potential"}

    sif_row = dist_df[dist_df["SIF Label"] == "SIF-potential"].iloc[0]
    assert sif_row["Count"] == 2
    assert sif_row["Percentage"] == 66.7


# ===========================================================================
# 6. Barrier failure Pareto + cumulative %
# ===========================================================================


def test_barrier_pareto(mock_dataset):
    pareto_df = get_barrier_pareto_data(mock_dataset)

    # Two valid barriers: LOTO Verification, Safe Zone Clearance
    assert len(pareto_df) == 2
    assert pareto_df.iloc[0]["Count"] == 1
    assert pareto_df.iloc[0]["Cumulative Percentage"] == 50.0
    assert pareto_df.iloc[1]["Cumulative Percentage"] == 100.0


def test_barrier_pareto_cumulative_is_monotonic(mock_dataset):
    pareto_df = get_barrier_pareto_data(mock_dataset)
    cum = pareto_df["Cumulative Percentage"].tolist()
    assert cum == sorted(cum), "Cumulative percentage should be non-decreasing"


# ===========================================================================
# 7. Life-Saving Rule counts
# ===========================================================================


def test_lsr_analysis(mock_dataset):
    lsr_df = get_lsr_analysis_data(mock_dataset)

    # Rules: Energy Isolation, Bypassing Safety Controls, Line of Fire, Safe Mechanical Lifting
    assert len(lsr_df) == 4
    for count in lsr_df["Count"]:
        assert count == 1

    # All rules come from SIF-potential reports → SIF Precursors = 1
    for precursors in lsr_df["SIF Precursors"]:
        assert precursors == 1


# ===========================================================================
# 8. Hazard / energy aggregation
# ===========================================================================


def test_hazard_energy_aggregation(mock_dataset):
    haz_data = get_hazard_energy_analysis_data(mock_dataset)

    assert "hazard" in haz_data
    assert "energy_source" in haz_data
    assert "exposure" in haz_data

    haz_df = haz_data["hazard"]
    assert "Electrical shock" in list(haz_df["Hazard"])
    assert "Suspended load" in list(haz_df["Hazard"])


# ===========================================================================
# 9. Site density calculation
# ===========================================================================


def test_site_safety_intelligence(mock_dataset):
    site_df = get_site_safety_intelligence_data(mock_dataset)

    assert len(site_df) == 2

    beta_row = site_df[site_df["Site"] == "Site Beta"].iloc[0]
    assert beta_row["Total Reports"] == 1
    assert beta_row["SIF Precursors"] == 1
    assert beta_row["SIF Density (%)"] == 100.0

    alpha_row = site_df[site_df["Site"] == "Site Alpha"].iloc[0]
    assert alpha_row["Total Reports"] == 2
    assert alpha_row["SIF Precursors"] == 1
    assert alpha_row["SIF Density (%)"] == 50.0

    # Sorted by density descending
    assert site_df.iloc[0]["SIF Density (%)"] >= site_df.iloc[-1]["SIF Density (%)"]


# ===========================================================================
# 10. Risk heatmap pivot matrix
# ===========================================================================


def test_risk_heatmap(mock_dataset):
    heatmap_df = get_risk_heatmap_data(mock_dataset, row_dim="site", col_dim="hazard")
    assert not heatmap_df.empty

    assert "Electrical shock" in heatmap_df.columns
    assert "Suspended load" in heatmap_df.columns
    assert "Site Alpha" in heatmap_df.index
    assert "Site Beta" in heatmap_df.index


def test_risk_heatmap_empty(empty_dataset):
    result = get_risk_heatmap_data(empty_dataset, row_dim="site", col_dim="hazard")
    assert result.empty


# ===========================================================================
# 11. Management insights
# ===========================================================================


def test_management_insights(mock_dataset):
    insights = generate_management_insights(mock_dataset)
    assert len(insights) > 0
    # Should flag the highest density site (Site Beta = 100 %)
    assert any("Site Beta" in ins for ins in insights)
    # Should mention at least one barrier name
    assert any("LOTO Verification" in ins or "Safe Zone Clearance" in ins for ins in insights)


def test_management_insights_single_report(mock_dataset):
    """Analytics must not crash or produce misleading output for a 1-row dataset."""
    single = mock_dataset.head(1)
    insights = generate_management_insights(single)
    assert isinstance(insights, list)
    assert len(insights) > 0


# ===========================================================================
# 12. Date filtering
# ===========================================================================


def test_date_filter_start_only(mock_dataset):
    """start_date = base_time - 7 days should return only reports from last 7 days."""
    base_time = datetime(2026, 8, 15, 10, 0, 0)
    cutoff = (base_time - timedelta(days=7)).date()

    filtered = filter_analytics_df(mock_dataset, start_date=cutoff)
    assert len(filtered) == 2  # reports 2 and 3 are within last 7 days


def test_date_filter_end_only(mock_dataset):
    """end_date before base_time should exclude report 3 (today)."""
    base_time = datetime(2026, 8, 15, 10, 0, 0)
    cutoff = (base_time - timedelta(days=1)).date()

    filtered = filter_analytics_df(mock_dataset, end_date=cutoff)
    assert len(filtered) == 2  # reports 1 and 2


def test_date_filter_range(mock_dataset):
    """Exact date range spanning only report 2."""
    base_time = datetime(2026, 8, 15, 10, 0, 0)
    d2 = (base_time - timedelta(days=5)).date()

    filtered = filter_analytics_df(mock_dataset, start_date=d2, end_date=d2)
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == 2


def test_date_filter_no_results(mock_dataset):
    """Future date range should return 0 results."""
    future = date(2030, 1, 1)
    filtered = filter_analytics_df(mock_dataset, start_date=future, end_date=future)
    assert len(filtered) == 0


# ===========================================================================
# 13. Keyword filtering
# ===========================================================================


def test_keyword_filter_original_text(mock_dataset):
    filtered = filter_analytics_df(mock_dataset, keyword="LOTO")
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == 1


def test_keyword_filter_hazard(mock_dataset):
    filtered = filter_analytics_df(mock_dataset, keyword="suspended")
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == 3


def test_keyword_filter_translated_text(mock_dataset):
    filtered = filter_analytics_df(mock_dataset, keyword="beneath crane")
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == 3


def test_keyword_filter_no_match(mock_dataset):
    filtered = filter_analytics_df(mock_dataset, keyword="nonexistent_xyz_abc")
    assert len(filtered) == 0


def test_keyword_filter_case_insensitive(mock_dataset):
    filtered_lower = filter_analytics_df(mock_dataset, keyword="loto")
    filtered_upper = filter_analytics_df(mock_dataset, keyword="LOTO")
    assert len(filtered_lower) == len(filtered_upper)


# ===========================================================================
# 14. Combined filters
# ===========================================================================


def test_combined_site_and_sif_filter(mock_dataset):
    filtered = filter_analytics_df(mock_dataset, site="Site Beta", sif_label="SIF-potential")
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == 3


def test_lsr_filter(mock_dataset):
    filtered = filter_analytics_df(mock_dataset, lsr_list=["Energy Isolation"])
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == 1


# ===========================================================================
# 15. CSV export
# ===========================================================================


def test_csv_export_returns_bytes(mock_dataset):
    result = export_to_csv(mock_dataset)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_csv_export_parseable(mock_dataset):
    csv_bytes = export_to_csv(mock_dataset)
    df_parsed = pd.read_csv(io.BytesIO(csv_bytes))
    assert len(df_parsed) == len(mock_dataset)


def test_csv_export_list_columns_serialized(mock_dataset):
    """List columns (resolved_life_saving_rules, evidence_phrases) must be
    serialized to comma-separated strings, not Python list literals."""
    csv_bytes = export_to_csv(mock_dataset)
    df_parsed = pd.read_csv(io.BytesIO(csv_bytes))

    if "resolved_life_saving_rules" in df_parsed.columns:
        for val in df_parsed["resolved_life_saving_rules"].dropna():
            assert not str(val).startswith("["), (
                f"List not serialized: {val!r}"
            )


def test_csv_export_empty_dataset(empty_dataset):
    """CSV export should not crash on empty DataFrame."""
    csv_bytes = export_to_csv(empty_dataset)
    assert isinstance(csv_bytes, bytes)
    df_parsed = pd.read_csv(io.BytesIO(csv_bytes))
    assert len(df_parsed) == 0


def test_csv_export_filtered_subset(mock_dataset):
    """CSV export should respect filtered data — only export matching rows."""
    filtered = filter_analytics_df(mock_dataset, site="Site Beta")
    csv_bytes = export_to_csv(filtered)
    df_parsed = pd.read_csv(io.BytesIO(csv_bytes))
    assert len(df_parsed) == 1
    assert df_parsed.iloc[0]["site"] == "Site Beta"
