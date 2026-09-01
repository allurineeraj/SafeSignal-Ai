import json
import sqlite3
import pandas as pd
import io
from datetime import datetime
from database.db import get_connection

def get_resolved_sif_and_priority_query():
    """Helper query snippet to get resolved SIF, priority, and other fields."""
    return """
        SELECT 
            r.id,
            r.created_at,
            r.report_type,
            r.site,
            r.location,
            r.original_text,
            r.translated_text,
            r.report_status,
            r.immediate_danger,
            r.review_priority,
            COALESCE(rev.final_sif_label, p.sif_label) as resolved_sif_label,
            COALESCE(rev.final_priority, p.priority) as resolved_priority,
            COALESCE(rev.final_activity, p.activity) as resolved_activity,
            COALESCE(rev.final_hazard, p.hazard) as resolved_hazard,
            COALESCE(rev.final_energy_source, p.energy_source) as resolved_energy_source,
            COALESCE(rev.final_exposure, p.exposure) as resolved_exposure,
            COALESCE(rev.final_failed_barrier, p.failed_barrier) as resolved_failed_barrier,
            COALESCE(rev.final_potential_consequence, p.potential_consequence) as resolved_potential_consequence,
            COALESCE(rev.final_life_saving_rules, p.life_saving_rules) as resolved_life_saving_rules,
            p.confidence as ai_confidence,
            p.sif_score as ai_sif_score,
            p.evidence_phrases,
            p.classifier_mode,
            p.model_version,
            p.llm_provider as ai_llm_provider,
            p.llm_model as ai_llm_model,
            p.llm_analysis_status as ai_llm_analysis_status,
            p.llm_confidence as ai_llm_confidence,
            p.actual_injury as ai_actual_injury,
            p.explanation as ai_explanation
        FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
    """

def has_failed_barrier(val):
    """Helper to check if a failed barrier value indicates a valid failure."""
    if not val or pd.isna(val):
        return False
    val_clean = str(val).strip().lower()
    if val_clean in ["none", "n/a", "no", "unknown — requires hse review", ""]:
        return False
    return True

# Note: Caching can be implemented using @st.cache_data for Streamlit apps
def get_analytics_df() -> pd.DataFrame:
    """Fetches all reports with resolved fields from the database and returns a Pandas DataFrame."""
    conn = get_connection()
    query = get_resolved_sif_and_priority_query()
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Parse JSON list columns
    def safe_json_load(val):
        if not val:
            return []
        try:
            return json.loads(val)
        except:
            # If comma separated string (fallback)
            if isinstance(val, str) and "," in val:
                return [x.strip() for x in val.split(",") if x.strip()]
            return [val] if val else []

    df['resolved_life_saving_rules'] = df['resolved_life_saving_rules'].apply(safe_json_load)
    # Also parse evidence_phrases if present
    if 'evidence_phrases' in df.columns:
        df['evidence_phrases'] = df['evidence_phrases'].apply(safe_json_load)
    return df


def filter_analytics_df(
    df: pd.DataFrame,
    start_date=None,
    end_date=None,
    site: str = None,
    report_type: str = None,
    sif_label: str = None,
    priority: str = None,
    status: str = None,
    immediate_danger: str = None,
    classifier_mode: str = None,
    lsr_list: list = None,
    keyword: str = None,
) -> pd.DataFrame:
    """
    Applies user-specified filters to the analytics dataframe.
    Returns a filtered copy.  All parameters except df are optional.
    """
    filtered = df.copy()

    # Date range — recompute mask each step to avoid index mismatch warnings
    if start_date is not None:
        dates = pd.to_datetime(filtered["created_at"]).dt.date
        filtered = filtered[dates >= start_date].copy()
    if end_date is not None:
        dates = pd.to_datetime(filtered["created_at"]).dt.date
        filtered = filtered[dates <= end_date].copy()

    if site and site != "All":
        filtered = filtered[filtered["site"] == site]

    if report_type and report_type != "All":
        filtered = filtered[filtered["report_type"] == report_type]

    if sif_label and sif_label != "All":
        filtered = filtered[filtered["resolved_sif_label"] == sif_label]

    if priority and priority != "All":
        filtered = filtered[filtered["resolved_priority"] == priority]

    if status and status != "All":
        filtered = filtered[filtered["report_status"] == status]

    if immediate_danger == "Yes":
        filtered = filtered[filtered["immediate_danger"] == 1]
    elif immediate_danger == "No":
        filtered = filtered[filtered["immediate_danger"] == 0]

    if classifier_mode and classifier_mode != "All":
        filtered = filtered[filtered["classifier_mode"] == classifier_mode]

    if lsr_list:
        filtered = filtered[
            filtered["resolved_life_saving_rules"].apply(
                lambda r: any(rule in r for rule in lsr_list)
            )
        ]

    if keyword:
        q = keyword.lower()
        search_cols = [
            "original_text", "translated_text",
            "resolved_hazard", "resolved_failed_barrier",
            "resolved_potential_consequence"
        ]
        text_mask = (
            filtered[search_cols]
            .fillna("")
            .apply(lambda col: col.str.lower().str.contains(q, regex=False))
            .any(axis=1)
        )
        lsr_mask = filtered["resolved_life_saving_rules"].apply(
            lambda r: any(q in rule.lower() for rule in r)
        )
        filtered = filtered[text_mask | lsr_mask]

    return filtered.reset_index(drop=True)


def export_to_csv(df: pd.DataFrame) -> bytes:
    """
    Exports the given DataFrame to a CSV bytes payload suitable for st.download_button.
    Formats list columns to comma-separated strings.
    """
    export_df = df.copy()
    if "resolved_life_saving_rules" in export_df.columns:
        export_df["resolved_life_saving_rules"] = export_df["resolved_life_saving_rules"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else (x or "")
        )
    if "evidence_phrases" in export_df.columns:
        export_df["evidence_phrases"] = export_df["evidence_phrases"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else (x or "")
        )
    return export_df.to_csv(index=False).encode("utf-8")


def calculate_kpi_metrics(df: pd.DataFrame) -> dict:
    """Calculates top-level KPI metrics from the reports dataframe."""
    total = len(df)
    if total == 0:
        return {
            "total_reports": 0,
            "sif_precursor_pct": 0.0,
            "critical_high_count": 0,
            "open_reviews_count": 0,
            "immediate_danger_count": 0,
            "barrier_failure_rate": 0.0
        }
        
    sif_count = df[df["resolved_sif_label"] == "SIF-potential"].shape[0]
    sif_precursor_pct = round((sif_count / total) * 100, 1)
    
    critical_high_count = df[df["resolved_priority"].isin(["Critical", "High"])].shape[0]
    
    open_reviews_count = df[df["report_status"] == "Pending HSE Review"].shape[0]
    
    immediate_danger_count = df[df["immediate_danger"] == 1].shape[0]
    
    # Calculate barrier failure rate: reports with a non-empty/non-none failed barrier / total
    barrier_fail_count = df[df["resolved_failed_barrier"].apply(has_failed_barrier)].shape[0]
    barrier_failure_rate = round((barrier_fail_count / total) * 100, 1)
    
    return {
        "total_reports": total,
        "sif_precursor_pct": sif_precursor_pct,
        "critical_high_count": critical_high_count,
        "open_reviews_count": open_reviews_count,
        "immediate_danger_count": immediate_danger_count,
        "barrier_failure_rate": barrier_failure_rate
    }

def get_sif_trend_data(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Aggregates reports over time (W = Weekly, ME = Monthly) grouped by SIF status."""
    if df.empty:
        return pd.DataFrame(columns=["Period", "Total", "SIF-potential", "Non-SIF-potential", "Review Required"])
        
    # Convert created_at to datetime
    df = df.copy()
    df["created_at_dt"] = pd.to_datetime(df["created_at"])
    
    # Group by frequency
    # Note: to_period() only accepts 'M' (not 'ME' which is resample-only)
    period_freq = "M" if freq in ("ME", "MS", "M") else freq
    df["Period"] = df["created_at_dt"].dt.to_period(period_freq).dt.start_time
    
    grouped = df.groupby(["Period", "resolved_sif_label"]).size().unstack(fill_value=0)
    
    # Reindex columns to ensure they exist
    for col in ["SIF-potential", "Non-SIF-potential", "Review Required"]:
        if col not in grouped.columns:
            grouped[col] = 0
            
    grouped["Total"] = grouped["SIF-potential"] + grouped["Non-SIF-potential"] + grouped["Review Required"]
    grouped = grouped.reset_index()
    
    # Format Period as String for easier plotting
    date_format = "%Y-%m-%d" if freq == "W" else "%Y-%b"
    grouped["Period_Str"] = grouped["Period"].dt.strftime(date_format)
    
    return grouped.sort_values("Period")

def get_sif_distribution_data(df: pd.DataFrame) -> pd.DataFrame:
    """Returns count and percentage of each SIF label."""
    if df.empty:
        return pd.DataFrame(columns=["SIF Label", "Count", "Percentage"])
        
    counts = df["resolved_sif_label"].value_counts().reset_index()
    counts.columns = ["SIF Label", "Count"]
    total = counts["Count"].sum()
    counts["Percentage"] = (counts["Count"] / total * 100).round(1)
    return counts

def get_barrier_pareto_data(df: pd.DataFrame) -> pd.DataFrame:
    """Returns failed barriers sorted by occurrence with cumulative percentage."""
    if df.empty:
        return pd.DataFrame(columns=["Barrier", "Count", "Cumulative Percentage"])
        
    # Extract barriers
    barriers = []
    for val in df["resolved_failed_barrier"].dropna():
        # Split by comma in case multiple are listed
        for b in val.split(","):
            b_clean = b.strip()
            if b_clean and b_clean.lower() not in ["none", "n/a", "unknown — requires hse review", "no"]:
                barriers.append(b_clean)
                
    if not barriers:
        return pd.DataFrame(columns=["Barrier", "Count", "Cumulative Percentage"])
        
    counts = pd.Series(barriers).value_counts().reset_index()
    counts.columns = ["Barrier", "Count"]
    
    total = counts["Count"].sum()
    counts["Cumulative Percentage"] = (counts["Count"].cumsum() / total * 100).round(1)
    
    return counts

def get_lsr_analysis_data(df: pd.DataFrame) -> pd.DataFrame:
    """Returns Life-Saving Rules count and their SIF-potential association."""
    if df.empty:
        return pd.DataFrame(columns=["Life-Saving Rule", "Count", "SIF Precursors", "Association %"])
        
    rules_list = []
    sif_rules_list = []
    
    for idx, row in df.iterrows():
        rules = row["resolved_life_saving_rules"]
        is_sif = row["resolved_sif_label"] == "SIF-potential"
        for r in rules:
            if r:
                rules_list.append(r)
                if is_sif:
                    sif_rules_list.append(r)
                    
    if not rules_list:
        return pd.DataFrame(columns=["Life-Saving Rule", "Count", "SIF Precursors", "Association %"])
        
    all_counts = pd.Series(rules_list).value_counts().reset_index()
    all_counts.columns = ["Life-Saving Rule", "Count"]
    
    sif_counts = pd.Series(sif_rules_list).value_counts().to_dict()
    
    all_counts["SIF Precursors"] = all_counts["Life-Saving Rule"].map(sif_counts).fillna(0).astype(int)
    all_counts["Association %"] = (all_counts["SIF Precursors"] / all_counts["Count"] * 100).round(1)
    
    return all_counts

def get_hazard_energy_analysis_data(df: pd.DataFrame) -> dict:
    """Aggregates hazards, energy sources and exposures, indicating SIF counts."""
    res = {"hazard": pd.DataFrame(), "energy_source": pd.DataFrame(), "exposure": pd.DataFrame()}
    
    for col in ["resolved_hazard", "resolved_energy_source", "resolved_exposure"]:
        key = col.replace("resolved_", "")
        if df.empty:
            res[key] = pd.DataFrame(columns=[key.capitalize(), "Count", "SIF-potential", "Non-SIF-potential", "Review Required"])
            continue
            
        # Clean empty strings and nan
        clean_df = df.copy()
        clean_df[col] = clean_df[col].fillna("None").astype(str).str.strip()
        clean_df.loc[clean_df[col] == "", col] = "None"
        
        grouped = clean_df.groupby([col, "resolved_sif_label"]).size().unstack(fill_value=0)
        
        # Ensure all SIF columns exist
        for sc in ["SIF-potential", "Non-SIF-potential", "Review Required"]:
            if sc not in grouped.columns:
                grouped[sc] = 0
                
        grouped["Count"] = grouped["SIF-potential"] + grouped["Non-SIF-potential"] + grouped["Review Required"]
        grouped = grouped.reset_index().rename(columns={col: key.capitalize()})
        res[key] = grouped.sort_values(by="Count", ascending=False)
        
    return res

def get_site_safety_intelligence_data(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates site-level safety metrics, sorted by SIF precursor density."""
    if df.empty:
        return pd.DataFrame(columns=["Site", "Total Reports", "SIF Precursors", "SIF Density (%)", "Critical/High", "Barrier Failures", "Immediate Danger"])
        
    sites = df["site"].unique()
    rows = []
    
    for site in sites:
        site_df = df[df["site"] == site]
        total = len(site_df)
        sif_count = site_df[site_df["resolved_sif_label"] == "SIF-potential"].shape[0]
        density = round((sif_count / total * 100), 1) if total > 0 else 0.0
        crit_high = site_df[site_df["resolved_priority"].isin(["Critical", "High"])].shape[0]
        
        barrier_fails = site_df[site_df["resolved_failed_barrier"].apply(has_failed_barrier)].shape[0]
        imm_danger = site_df[site_df["immediate_danger"] == 1].shape[0]
        
        rows.append({
            "Site": site,
            "Total Reports": total,
            "SIF Precursors": sif_count,
            "SIF Density (%)": density,
            "Critical/High": crit_high,
            "Barrier Failures": barrier_fails,
            "Immediate Danger": imm_danger
        })
        
    res_df = pd.DataFrame(rows)
    return res_df.sort_values(by="SIF Density (%)", ascending=False).reset_index(drop=True)

def get_risk_heatmap_data(df: pd.DataFrame, row_dim: str = "site", col_dim: str = "hazard") -> pd.DataFrame:
    """Generates pivot table of co-occurrences between two dimensions."""
    if df.empty:
        return pd.DataFrame()
        
    col_mapping = {
        "site": "site",
        "report_type": "report_type",
        "life_saving_rule": "resolved_life_saving_rules",
        "hazard": "resolved_hazard",
        "energy_source": "resolved_energy_source",
        "exposure": "resolved_exposure"
    }
    
    row_col = col_mapping.get(row_dim)
    col_col = col_mapping.get(col_dim)
    
    if not row_col or not col_col or row_col not in df.columns or col_col not in df.columns:
        return pd.DataFrame()
        
    # Build row_field and col_field safely — operate on original column names to
    # avoid rename collisions when both dims are life_saving_rule.
    temp_df = df[["id", row_col, col_col]].copy() if row_col != col_col else df[["id", row_col]].copy()

    # --- row_field ---
    if row_dim == "life_saving_rule":
        temp_df = temp_df.explode(row_col).reset_index(drop=True)
    temp_df["row_field"] = temp_df[row_col].fillna("None").apply(
        lambda v: str(v).strip() or "None"
    )

    # --- col_field ---
    if col_dim == "life_saving_rule":
        temp_df = temp_df.explode(col_col).reset_index(drop=True)
    temp_df["col_field"] = temp_df[col_col].fillna("None").apply(
        lambda v: str(v).strip() or "None"
    )

    # Generate pivot — reset_index to clear any duplicate labels from explode
    temp_df = temp_df[["row_field", "col_field"]].dropna().reset_index(drop=True)
    if temp_df.empty:
        return pd.DataFrame()
    pivot = pd.crosstab(temp_df["row_field"], temp_df["col_field"])
    return pivot

def generate_management_insights(df: pd.DataFrame) -> list[str]:
    """Generates a list of data-driven safety insights and recommendations."""
    insights = []
    
    if df.empty:
        return ["No safety reports recorded in the database yet. Insights will appear when reports are submitted."]
        
    total = len(df)
    
    # 1. SIF Precursor Density Insight
    sif_df = df[df["resolved_sif_label"] == "SIF-potential"]
    sif_count = len(sif_df)
    sif_pct = (sif_count / total * 100) if total > 0 else 0
    if sif_pct > 30:
        insights.append(f"High SIF Precursor Density detected ({sif_pct:.1f}% of total reports). The system suggests focusing preventive resources on high-potential hazard areas.")
    elif sif_pct > 0:
        insights.append(f"SIF Precursor Density is currently at {sif_pct:.1f}%. Ongoing monitoring is recommended for all high-risk operations.")
        
    # 2. Site Insight
    site_stats = get_site_safety_intelligence_data(df)
    if not site_stats.empty and site_stats.iloc[0]["SIF Precursors"] > 0:
        top_site = site_stats.iloc[0]["Site"]
        top_site_density = site_stats.iloc[0]["SIF Density (%)"]
        insights.append(f"Site '{top_site}' exhibits the highest reported SIF precursor density at {top_site_density:.1f}%. We recommend targeted safety audits at this location.")

    # 3. Failed Barrier Insight
    barrier_stats = get_barrier_pareto_data(df)
    if not barrier_stats.empty:
        top_barrier = barrier_stats.iloc[0]["Barrier"]
        top_barrier_count = barrier_stats.iloc[0]["Count"]
        insights.append(f"'{top_barrier}' is the most frequently bypassed or failed barrier, appearing in {top_barrier_count} reports. Consider reinforcing training or operating procedures surrounding this control.")
        
    # 4. Life-Saving Rule Insight
    lsr_stats = get_lsr_analysis_data(df)
    if not lsr_stats.empty:
        top_rule = lsr_stats.iloc[0]["Life-Saving Rule"]
        top_rule_pct = lsr_stats.iloc[0]["Association %"]
        insights.append(f"Violations associated with the Life-Saving Rule '{top_rule}' have a {top_rule_pct:.1f}% rate of SIF-potential classification, representing the highest rule-based risk pathway.")
        
    # 5. Immediate Danger Insight
    danger_count = df[df["immediate_danger"] == 1].shape[0]
    if danger_count > 0:
        insights.append(f"Action required: There are currently {danger_count} reports active with Immediate Danger flags. Ensure immediate field verification and mitigation.")

    if not insights:
        insights.append("Reporting is currently stable with no anomalous safety trends or critical rule violations observed.")
        
    return insights
