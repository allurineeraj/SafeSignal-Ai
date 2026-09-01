"""
Report Explorer – SIF-Insight Phase 5
======================================
Professional searchable report investigation interface backed by the analytics
service layer.  All analytics calls use cached data.  Filtering is delegated to
the testable `filter_analytics_df` helper in `services.analytics`.
"""

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from database.db import get_audit_trail, get_report_by_id
from services.analytics import (
    export_to_csv,
    filter_analytics_df,
    get_analytics_df,
)
from services.similar_search import find_similar_reports

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Report Explorer – SIF-Insight",
    page_icon="🔎",
    layout="wide",
)

# ---------------------------------------------------------------------------
# CSS – professional industrial-safety styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ─── Global ─────────────────────────────────────────────── */
    [data-testid="stAppViewContainer"] {
        background: #0d1117;
        color: #e6edf3;
    }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* ─── Page header ─────────────────────────────────────────── */
    .page-header {
        background: linear-gradient(135deg, #1a2332 0%, #0d1117 100%);
        border-left: 4px solid #2563eb;
        padding: 1.25rem 1.5rem;
        border-radius: 6px;
        margin-bottom: 1.5rem;
    }
    .page-header h1 { color: #e6edf3; font-size: 1.6rem; margin: 0; font-weight: 700; }
    .page-header p  { color: #8b949e; margin: 0.25rem 0 0; font-size: 0.9rem; }

    /* ─── Risk badges ─────────────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 0.2em 0.65em;
        font-size: 0.78em;
        font-weight: 600;
        border-radius: 4px;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .badge-sif     { background: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c; }
    .badge-nonsif  { background: #14532d; color: #86efac; border: 1px solid #16a34a; }
    .badge-review  { background: #78350f; color: #fcd34d; border: 1px solid #d97706; }
    .badge-critical{ background: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c; }
    .badge-high    { background: #7c2d12; color: #fdba74; border: 1px solid #ea580c; }
    .badge-medium  { background: #78350f; color: #fcd34d; border: 1px solid #d97706; }
    .badge-low     { background: #1e3a5f; color: #93c5fd; border: 1px solid #3b82f6; }

    /* ─── Filter panel ────────────────────────────────────────── */
    .filter-panel {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
    }
    .filter-panel-title {
        color: #8b949e;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
    }

    /* ─── Results counter ─────────────────────────────────────── */
    .results-bar {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .results-count { color: #2563eb; font-weight: 700; font-size: 1rem; }

    /* ─── Detail card ─────────────────────────────────────────── */
    .detail-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }
    .detail-card h3 { color: #2563eb; margin-top: 0; font-size: 1rem; }
    .detail-label   { color: #8b949e; font-size: 0.82rem; margin-bottom: 0.1rem; }
    .detail-value   { color: #e6edf3; font-size: 0.93rem; margin-bottom: 0.75rem; }

    /* ─── Evidence pill ───────────────────────────────────────── */
    .evidence-pill {
        display: inline-block;
        background: #1e3a5f;
        color: #93c5fd;
        border: 1px solid #3b82f6;
        border-radius: 12px;
        padding: 0.15em 0.55em;
        font-size: 0.78em;
        margin: 0.15em 0.2em;
    }

    /* ─── Section divider ─────────────────────────────────────── */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, #2563eb33, transparent);
        margin: 1.5rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar – demo role selector
# ---------------------------------------------------------------------------
if "user_role" not in st.session_state:
    st.session_state.user_role = "HSE Officer"

st.sidebar.markdown("### 🛠️ DEMO CONTROLS")
role_options = ["Worker / Observer", "Supervisor", "HSE Officer", "HSE Manager", "Administrator"]
selected_role = st.sidebar.selectbox(
    "Active Role", role_options, index=role_options.index(st.session_state.user_role)
)
if selected_role != st.session_state.user_role:
    st.session_state.user_role = selected_role
    st.rerun()

st.sidebar.info(f"Viewing as: **{st.session_state.user_role}**")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-header">
        <h1>🔎 Safety Report Explorer</h1>
        <p>Query, filter, and deep-inspect safety reports and AI classification records.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data (cached at Streamlit level)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def _load_data():
    return get_analytics_df()

df = _load_data()

if df.empty:
    st.warning(
        "⚠️ No safety reports found in the database.  "
        "Submit a report via the Worker Submission page to populate the explorer."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Helper badge renderers
# ---------------------------------------------------------------------------
def sif_badge_html(label: str) -> str:
    cls_map = {
        "SIF-potential": "badge-sif",
        "Non-SIF-potential": "badge-nonsif",
        "Review Required": "badge-review",
    }
    cls = cls_map.get(label, "badge-review")
    return f'<span class="badge {cls}">{label}</span>'


def priority_badge_html(label: str) -> str:
    cls_map = {
        "Critical": "badge-critical",
        "High": "badge-high",
        "Medium": "badge-medium",
        "Low": "badge-low",
    }
    cls = cls_map.get(label, "badge-low")
    return f'<span class="badge {cls}">{label}</span>'


# ---------------------------------------------------------------------------
# FILTERS & SEARCH
# ---------------------------------------------------------------------------
st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
st.markdown('<div class="filter-panel-title">🔍 Search & Filter Options</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    search_query = st.text_input(
        "Keyword Search",
        placeholder="Text, hazard, barrier, consequence, evidence…",
        key="re_keyword",
    )

    min_dt = pd.to_datetime(df["created_at"]).min().date()
    max_dt = pd.to_datetime(df["created_at"]).max().date()
    date_range = st.date_input(
        "Date Range",
        value=(min_dt, max_dt),
        min_value=min_dt,
        max_value=max_dt,
        key="re_daterange",
    )

    sites = ["All"] + sorted(df["site"].dropna().unique().tolist())
    selected_site = st.selectbox("Site", sites, key="re_site")

with col2:
    report_types = ["All"] + sorted(df["report_type"].dropna().unique().tolist())
    selected_type = st.selectbox("Report Type", report_types, key="re_type")

    sif_options = ["All"] + sorted(df["resolved_sif_label"].dropna().unique().tolist())
    selected_sif = st.selectbox("SIF Classification", sif_options, key="re_sif")

    priority_options = ["All"] + sorted(df["resolved_priority"].dropna().unique().tolist())
    selected_priority = st.selectbox("Priority Level", priority_options, key="re_priority")

with col3:
    status_options = ["All"] + sorted(df["report_status"].dropna().unique().tolist())
    selected_status = st.selectbox("Workflow Status", status_options, key="re_status")

    selected_danger = st.selectbox("Immediate Danger?", ["All", "Yes", "No"], key="re_danger")

    mode_options = ["All"] + sorted(df["classifier_mode"].dropna().unique().tolist())
    selected_mode = st.selectbox("Classifier Mode", mode_options, key="re_mode")

# LSR multi-select
all_lsrs = sorted(
    {rule for rules in df["resolved_life_saving_rules"] for rule in rules if rule}
)
selected_lsrs = st.multiselect("Filter by Life-Saving Rule(s)", all_lsrs, key="re_lsr")

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Apply filters via service function
# ---------------------------------------------------------------------------
start_date = date_range[0] if isinstance(date_range, (list, tuple)) and len(date_range) >= 1 else None
end_date   = date_range[1] if isinstance(date_range, (list, tuple)) and len(date_range) >= 2 else None

filtered_df = filter_analytics_df(
    df=df,
    start_date=start_date,
    end_date=end_date,
    site=selected_site,
    report_type=selected_type,
    sif_label=selected_sif,
    priority=selected_priority,
    status=selected_status,
    immediate_danger=selected_danger,
    classifier_mode=selected_mode,
    lsr_list=selected_lsrs if selected_lsrs else None,
    keyword=search_query if search_query.strip() else None,
)

# ---------------------------------------------------------------------------
# Results counter + export
# ---------------------------------------------------------------------------
exp_col, dl_col = st.columns([3, 1])
with exp_col:
    colour = "#2563eb" if len(filtered_df) > 0 else "#ef4444"
    st.markdown(
        f'<p style="color:{colour};font-weight:700;font-size:1.05rem;">'
        f"📋 {len(filtered_df)} report(s) match current filters"
        f"</p>",
        unsafe_allow_html=True,
    )

with dl_col:
    if not filtered_df.empty:
        csv_bytes = export_to_csv(filtered_df)
        st.download_button(
            label="📥 Export CSV",
            data=csv_bytes,
            file_name=f"sif_insight_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            width='stretch',
        )

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------
if filtered_df.empty:
    st.info("ℹ️ No reports match the selected filters.  Adjust the search criteria above.")
else:
    # Build display table with badge columns
    table_rows = []
    for _, row in filtered_df.iterrows():
        lsr_text = ", ".join(row["resolved_life_saving_rules"]) if row["resolved_life_saving_rules"] else "—"
        table_rows.append(
            {
                "ID": row["id"],
                "Date": pd.to_datetime(row["created_at"]).strftime("%Y-%m-%d"),
                "Site": row["site"] or "—",
                "Type": row["report_type"] or "—",
                "SIF Label": row["resolved_sif_label"] or "—",
                "Score": f"{int(row['ai_sif_score'])}/10" if pd.notna(row.get("ai_sif_score")) else "—",
                "Priority": row["resolved_priority"] or "—",
                "Hazard": (str(row["resolved_hazard"])[:40] + "…") if row.get("resolved_hazard") and len(str(row["resolved_hazard"])) > 40 else (row.get("resolved_hazard") or "—"),
                "Failed Barrier": (str(row["resolved_failed_barrier"])[:40] + "…") if row.get("resolved_failed_barrier") and len(str(row["resolved_failed_barrier"])) > 40 else (row.get("resolved_failed_barrier") or "—"),
                "Life-Saving Rule": (lsr_text[:50] + "…") if len(lsr_text) > 50 else lsr_text,
                "Status": row["report_status"] or "—",
                "⚠️ Danger": "🔴 YES" if row.get("immediate_danger") == 1 else "—",
            }
        )

    table_df = pd.DataFrame(table_rows)
    st.dataframe(table_df, width='stretch', hide_index=True, height=380)

    # -----------------------------------------------------------------------
    # Detailed report inspector
    # -----------------------------------------------------------------------
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.subheader("🔎 Detailed Report Inspector")

    report_ids = sorted(filtered_df["id"].unique().tolist())
    selected_id = st.selectbox(
        "Select Report ID to inspect:",
        report_ids,
        format_func=lambda x: f"Report #{x}",
        key="re_selected_id",
    )

    if selected_id:
        rep = get_report_by_id(selected_id)
        if rep is None:
            st.error(f"Report #{selected_id} could not be loaded from the database.")
        else:
            is_worker = st.session_state.user_role == "Worker / Observer"

            # ── Row 1: narrative + AI assessment ──────────────────────────
            left, right = st.columns(2)

            with left:
                st.markdown(
                    f'<div class="detail-card">'
                    f'<h3>📄 Report #{rep["id"]} — Narrative</h3>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<p class="detail-label">Report Type</p>'
                    f'<p class="detail-value">{rep["report_type"]}</p>'
                    f'<p class="detail-label">Site / Location</p>'
                    f'<p class="detail-value">{rep["site"]} › {rep["location"]}</p>'
                    f'<p class="detail-label">Submitted At</p>'
                    f'<p class="detail-value">{rep["created_at"]}</p>'
                    f'<p class="detail-label">Reporter</p>'
                    f'<p class="detail-value">{"Anonymous" if rep.get("anonymous") == 1 or is_worker else (rep.get("submitted_by") or "Unknown")}</p>',
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown('<div class="detail-card">', unsafe_allow_html=True)
                st.markdown("**Original Narrative**")
                st.info(rep.get("original_text") or "_(no text)_")
                if rep.get("translated_text"):
                    st.markdown("**Translated Text**")
                    st.caption(rep["translated_text"])
                if rep.get("immediate_action"):
                    st.markdown("**Immediate Action Taken**")
                    st.write(rep["immediate_action"])
                st.markdown("</div>", unsafe_allow_html=True)

            with right:
                # Resolved values
                sif_val  = rep.get("final_sif_label")  or rep.get("ai_sif_label")  or "N/A"
                prio_val = rep.get("final_priority")    or rep.get("ai_priority")   or "N/A"
                reviewed = bool(rep.get("review_status"))

                st.markdown(
                    f'<div class="detail-card"><h3>🤖 AI & HSE Assessment</h3>',
                    unsafe_allow_html=True,
                )
                m1, m2, m3 = st.columns(3)
                m1.metric("SIF Label", sif_val)
                m2.metric("Priority", prio_val)
                m3.metric("Status", rep.get("report_status", "—"))

                score = rep.get("ai_sif_score")
                conf  = rep.get("ai_confidence")
                st.markdown(
                    f'<p class="detail-label">AI Score</p>'
                    f'<p class="detail-value">'
                    f'{"%.0f" % score}/10' if score is not None else "N/A"
                    f'</p>',
                    unsafe_allow_html=True,
                )
                st.write(
                    f"**ML Confidence:** "
                    f"{'%.0f%%' % (conf * 100) if conf is not None else 'Not available'} | "
                    f"**Mode:** {rep.get('ai_classifier_mode', '—')} "
                    f"(v{rep.get('ai_model_version', '—')})"
                )
                st.markdown("</div>", unsafe_allow_html=True)

                # Safety elements
                act   = (rep.get("final_activity")           if reviewed else rep.get("ai_activity"))           or "—"
                haz   = (rep.get("final_hazard")             if reviewed else rep.get("ai_hazard"))             or "—"
                eng   = (rep.get("final_energy_source")      if reviewed else rep.get("ai_energy_source"))      or "—"
                exp   = (rep.get("final_exposure")           if reviewed else rep.get("ai_exposure"))           or "—"
                bar   = (rep.get("final_failed_barrier")     if reviewed else rep.get("ai_failed_barrier"))     or "—"
                con   = (rep.get("final_potential_consequence") if reviewed else rep.get("ai_potential_consequence")) or "—"
                rules = (rep.get("final_life_saving_rules")  if reviewed else rep.get("ai_life_saving_rules"))  or []
                evid  = rep.get("ai_evidence_phrases") or []

                st.markdown(
                    f'<div class="detail-card"><h3>⚠️ Identified Safety Elements</h3>'
                    f'<p class="detail-label">Activity</p><p class="detail-value">{act}</p>'
                    f'<p class="detail-label">Hazard</p><p class="detail-value">{haz}</p>'
                    f'<p class="detail-label">Energy Source</p><p class="detail-value">{eng}</p>'
                    f'<p class="detail-label">Exposure</p><p class="detail-value">{exp}</p>'
                    f'<p class="detail-label">Failed Barrier</p><p class="detail-value">{bar}</p>'
                    f'<p class="detail-label">Potential Consequence</p><p class="detail-value">{con}</p>'
                    f'<p class="detail-label">Life-Saving Rules</p>'
                    f'<p class="detail-value">{", ".join(rules) if rules else "None matched"}</p>',
                    unsafe_allow_html=True,
                )
                if evid:
                    pills = "".join(f'<span class="evidence-pill">{e}</span>' for e in evid)
                    st.markdown(
                        f'<p class="detail-label">Evidence Phrases</p><p>{pills}</p>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

            # ── HSE review comments ────────────────────────────────────────
            if rep.get("hse_comments"):
                st.markdown(
                    f'<div class="detail-card"><h3>💬 HSE Reviewer Comments</h3>'
                    f'<p class="detail-value">{rep["hse_comments"]}</p></div>',
                    unsafe_allow_html=True,
                )

            # ── Audit trail ────────────────────────────────────────────────
            with st.expander("📋 Audit & Review History", expanded=False):
                audit_logs = get_audit_trail(selected_id)
                if audit_logs:
                    hist = [
                        {
                            "Timestamp":       log["timestamp"],
                            "User":            log["user_name"],
                            "Role":            log["role"],
                            "Action":          log["action"],
                            "Field":           log.get("field_name") or "—",
                            "Old Value":       log.get("old_value")  or "—",
                            "New Value":       log.get("new_value")  or "—",
                        }
                        for log in audit_logs
                    ]
                    st.dataframe(pd.DataFrame(hist), width='stretch', hide_index=True)
                else:
                    st.write("No audit trail entries found for this report.")
            
            # ── Similar Reports (TF-IDF Cosine Similarity) ────────────────────────────────
            with st.expander("🔗 Similar Reports (AI-Powered)", expanded=False):
                with st.spinner("Finding similar reports..."):
                    similar_reports = find_similar_reports(selected_id, rep.get("original_text", ""))
                    if similar_reports:
                        for sim in similar_reports:
                            sim_pct = sim['similarity_score'] * 100
                            st.markdown(f"**Report #{sim['id']}** ({sim['report_type']}) — *Similarity: {sim_pct:.1f}%*")
                            st.caption(f"{sim['original_text']}")
                            st.divider()
                    else:
                        st.write("No similar reports found with a significant match score.")
