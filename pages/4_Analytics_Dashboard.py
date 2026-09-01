"""
Analytics Dashboard – SIF-Insight Phase 5
==========================================
A professional safety-intelligence dashboard driven exclusively from the
SQLite database through the analytics service layer.  All KPIs, charts, and
management insights reflect real reported data.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.analytics import (
    calculate_kpi_metrics,
    generate_management_insights,
    get_analytics_df,
    get_barrier_pareto_data,
    get_hazard_energy_analysis_data,
    get_lsr_analysis_data,
    get_risk_heatmap_data,
    get_sif_distribution_data,
    get_sif_trend_data,
    get_site_safety_intelligence_data,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Analytics Dashboard – SIF-Insight",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Design tokens & CSS
# ---------------------------------------------------------------------------
PALETTE = {
    "sif": "#ef4444",
    "non_sif": "#22c55e",
    "review": "#f59e0b",
    "total": "#6b7280",
    "blue": "#3b82f6",
    "dark_bg": "#0d1117",
    "card_bg": "#161b22",
    "border": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
}

st.markdown(
    f"""
    <style>
    /* ─── Global ─────────────────────────────────────────────── */
    [data-testid="stAppViewContainer"] {{
        background: {PALETTE['dark_bg']};
        color: {PALETTE['text']};
    }}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}

    /* ─── KPI card ────────────────────────────────────────────── */
    .kpi-card {{
        background: {PALETTE['card_bg']};
        border: 1px solid {PALETTE['border']};
        border-radius: 8px;
        padding: 1rem 1.25rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }}
    .kpi-card::before {{
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }}
    .kpi-card.danger::before  {{ background: {PALETTE['sif']}; }}
    .kpi-card.warning::before {{ background: {PALETTE['review']}; }}
    .kpi-card.safe::before    {{ background: {PALETTE['non_sif']}; }}
    .kpi-card.info::before    {{ background: {PALETTE['blue']}; }}
    .kpi-card.neutral::before {{ background: {PALETTE['total']}; }}

    .kpi-value {{
        font-size: 2rem;
        font-weight: 800;
        color: {PALETTE['text']};
        line-height: 1.1;
    }}
    .kpi-label {{
        font-size: 0.78rem;
        color: {PALETTE['muted']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.3rem;
    }}
    .kpi-sub {{
        font-size: 0.72rem;
        color: {PALETTE['muted']};
        margin-top: 0.2rem;
    }}

    /* ─── Section header ──────────────────────────────────────── */
    .section-header {{
        border-left: 3px solid {PALETTE['blue']};
        padding-left: 0.75rem;
        margin: 1.75rem 0 1rem;
    }}
    .section-header h2 {{
        color: {PALETTE['text']};
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0;
    }}
    .section-header p {{
        color: {PALETTE['muted']};
        font-size: 0.82rem;
        margin: 0.2rem 0 0;
    }}

    /* ─── Insight card ────────────────────────────────────────── */
    .insight-card {{
        background: {PALETTE['card_bg']};
        border-left: 3px solid {PALETTE['blue']};
        border-radius: 6px;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.65rem;
        font-size: 0.9rem;
        color: {PALETTE['text']};
    }}

    /* ─── Risk badge ──────────────────────────────────────────── */
    .rbadge {{
        display: inline-block;
        padding: 0.2em 0.6em;
        border-radius: 4px;
        font-size: 0.75em;
        font-weight: 600;
        text-transform: uppercase;
    }}
    .rbadge-sif  {{ background: #7f1d1d; color: #fca5a5; }}
    .rbadge-hi   {{ background: #7c2d12; color: #fdba74; }}
    .rbadge-med  {{ background: #78350f; color: #fcd34d; }}
    .rbadge-low  {{ background: #1e3a5f; color: #93c5fd; }}

    /* ─── Disclaimer ──────────────────────────────────────────── */
    .disclaimer {{
        background: #1e2a3a;
        border: 1px solid #3b82f6;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        font-size: 0.78rem;
        color: {PALETTE['muted']};
        margin-top: 1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Plotly layout defaults (dark theme)
# ---------------------------------------------------------------------------
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(22,27,34,1)",
    font_color="#c9d1d9",
    font_size=12,
    margin=dict(l=40, r=40, t=55, b=50),
    legend=dict(
        bgcolor="rgba(22,27,34,0.8)",
        bordercolor="#30363d",
        borderwidth=1,
        font=dict(size=11),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    ),
    xaxis=dict(gridcolor="#21262d", linecolor="#30363d"),
    yaxis=dict(gridcolor="#21262d", linecolor="#30363d"),
)


def apply_layout(fig, title: str, **extra):
    fig.update_layout(title=dict(text=title, font=dict(size=13, color="#e6edf3")), **PLOTLY_LAYOUT, **extra)
    return fig


# ---------------------------------------------------------------------------
# Sidebar – demo role selector
# ---------------------------------------------------------------------------
if "user_role" not in st.session_state:
    st.session_state.user_role = "HSE Officer"

st.sidebar.markdown("### 🛠️ DEMO CONTROLS")
role_options = ["Worker / Observer", "Supervisor", "HSE Officer", "HSE Manager", "Administrator"]
sel_role = st.sidebar.selectbox(
    "Active Role", role_options, index=role_options.index(st.session_state.user_role)
)
if sel_role != st.session_state.user_role:
    st.session_state.user_role = sel_role
    st.rerun()

st.sidebar.info(f"Viewing as: **{st.session_state.user_role}**")

# Time filter in sidebar
st.sidebar.markdown("### 📅 Dashboard Time Filter")
@st.cache_data(ttl=120, show_spinner=False)
def _load_df():
    return get_analytics_df()

df_all = _load_df()

if not df_all.empty:
    min_dt = pd.to_datetime(df_all["created_at"]).min().date()
    max_dt = pd.to_datetime(df_all["created_at"]).max().date()
    dash_dates = st.sidebar.date_input(
        "Date range",
        value=(min_dt, max_dt),
        min_value=min_dt,
        max_value=max_dt,
        key="dash_daterange",
    )
    if isinstance(dash_dates, (list, tuple)) and len(dash_dates) == 2:
        d_start, d_end = dash_dates
        df_dates = pd.to_datetime(df_all["created_at"]).dt.date
        df = df_all[(df_dates >= d_start) & (df_dates <= d_end)].copy()
    else:
        df = df_all.copy()

    site_opts = ["All Sites"] + sorted(df_all["site"].dropna().unique().tolist())
    dash_site = st.sidebar.selectbox("Site", site_opts, key="dash_site")
    if dash_site != "All Sites":
        df = df[df["site"] == dash_site]
else:
    df = df_all.copy()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div style="background:linear-gradient(135deg,#1a2332 0%,#0d1117 100%);
         border-left:4px solid #2563eb;padding:1.25rem 1.5rem;border-radius:6px;margin-bottom:1.5rem;">
        <h1 style="color:#e6edf3;font-size:1.6rem;margin:0;font-weight:700;">📊 Safety Intelligence Dashboard</h1>
        <p style="color:#8b949e;margin:0.25rem 0 0;font-size:0.9rem;">
            Real-time SIF analysis, barrier failures, and site risk intelligence driven from the live database.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Empty-state guard
# ---------------------------------------------------------------------------
if df.empty:
    st.warning(
        "⚠️ No safety reports match the selected date range/site filter.  "
        "Adjust the sidebar filters or submit reports via the Worker Submission page."
    )
    st.stop()

# ===========================================================================
# SECTION 1 – KPI CARDS
# ===========================================================================
st.markdown(
    '<div class="section-header"><h2>📌 Key Performance Indicators</h2>'
    '<p>Calculated from database records matching current filters.</p></div>',
    unsafe_allow_html=True,
)

kpis = calculate_kpi_metrics(df)

k1, k2, k3, k4, k5, k6 = st.columns(6)

def _kpi(col, value, label, sub, accent):
    col.markdown(
        f'<div class="kpi-card {accent}">'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

_kpi(k1, kpis["total_reports"],            "Total Reports",         "All submissions",               "neutral")
_kpi(k2, f"{kpis['sif_precursor_pct']}%",  "SIF Precursor %",       "% of total reports",            "danger")
_kpi(k3, kpis["critical_high_count"],       "Critical / High Risk",  "Priority level",                "warning")
_kpi(k4, kpis["open_reviews_count"],        "Pending HSE Review",    "Awaiting assessment",           "warning")
_kpi(k5, kpis["immediate_danger_count"],    "Immediate Danger",      "Active danger flags",           "danger")
_kpi(k6, f"{kpis['barrier_failure_rate']}%","Barrier Failure Rate",  "Reports w/ failed barrier",     "info")

st.markdown("<br>", unsafe_allow_html=True)

# ===========================================================================
# SECTION 2 – SIF TREND + DISTRIBUTION
# ===========================================================================
st.markdown(
    '<div class="section-header"><h2>📈 SIF Precursor Trend & Risk Distribution</h2>'
    '<p>Reporting volume and SIF classification over time.</p></div>',
    unsafe_allow_html=True,
)

trend_col, dist_col = st.columns([7, 3])

with trend_col:
    freq_option = st.radio(
        "Aggregation", ["Weekly", "Monthly"], horizontal=True, key="dash_freq"
    )
    freq_code = "W" if freq_option == "Weekly" else "ME"
    trend_df = get_sif_trend_data(df, freq=freq_code)

    if trend_df.empty or len(trend_df) < 2:
        st.info(
            "Insufficient historical data for time-series trend "
            f"({freq_option.lower()} aggregation requires observations spanning multiple periods)."
        )
    else:
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=trend_df["Period"], y=trend_df["Total"],
            name="Total Reports",
            line=dict(color=PALETTE["total"], width=2, dash="dot"),
            fill="tozeroy", fillcolor="rgba(107,114,128,0.08)",
        ))
        fig_trend.add_trace(go.Scatter(
            x=trend_df["Period"], y=trend_df["SIF-potential"],
            name="SIF-Potential",
            line=dict(color=PALETTE["sif"], width=3),
            mode="lines+markers",
        ))
        fig_trend.add_trace(go.Scatter(
            x=trend_df["Period"], y=trend_df["Review Required"],
            name="Review Required",
            line=dict(color=PALETTE["review"], width=2, dash="dash"),
        ))
        apply_layout(
            fig_trend,
            f"Reporting Volume & SIF Precursor Trend ({freq_option})",
            yaxis_title="Reports",
        )
        st.plotly_chart(fig_trend, width='stretch')

with dist_col:
    dist_df = get_sif_distribution_data(df)
    if dist_df.empty:
        st.info("No classification data available.")
    else:
        fig_dist = px.pie(
            dist_df,
            values="Count",
            names="SIF Label",
            hole=0.45,
            color="SIF Label",
            color_discrete_map={
                "SIF-potential":     PALETTE["sif"],
                "Review Required":   PALETTE["review"],
                "Non-SIF-potential": PALETTE["non_sif"],
            },
        )
        apply_layout(fig_dist, "Risk Classification Split")
        fig_dist.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
        )
        st.plotly_chart(fig_dist, width='stretch')

# ===========================================================================
# SECTION 3 – BARRIER FAILURE PARETO
# ===========================================================================
st.markdown(
    '<div class="section-header"><h2>🛡️ Failed Barrier Pareto Analysis</h2>'
    '<p>Which failed barriers are driving the largest share of safety risk? '
    '(80 % reference line shown)</p></div>',
    unsafe_allow_html=True,
)

pareto_df = get_barrier_pareto_data(df)

if pareto_df.empty:
    st.info("No barrier failure data recorded yet.  This chart populates as barriers are identified in reports.")
else:
    # Truncate long names for display
    pareto_df = pareto_df.copy()
    pareto_df["Barrier_Short"] = pareto_df["Barrier"].apply(
        lambda x: x[:35] + "…" if len(x) > 35 else x
    )

    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(
        x=pareto_df["Barrier_Short"],
        y=pareto_df["Count"],
        name="Failure Count",
        marker=dict(
            color=pareto_df["Cumulative Percentage"].apply(
                lambda p: PALETTE["sif"] if p <= 80 else PALETTE["total"]
            ),
            line=dict(width=0),
        ),
        hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>",
    ))
    fig_pareto.add_trace(go.Scatter(
        x=pareto_df["Barrier_Short"],
        y=pareto_df["Cumulative Percentage"],
        name="Cumulative %",
        yaxis="y2",
        line=dict(color="#f59e0b", width=2.5),
        mode="lines+markers",
        marker=dict(size=6),
        hovertemplate="Cumulative: %{y:.1f}%<extra></extra>",
    ))
    # 80 % Pareto line
    fig_pareto.add_shape(
        type="line",
        x0=-0.5, y0=80, x1=len(pareto_df) - 0.5, y1=80,
        yref="y2",
        line=dict(color="#f59e0b", width=1.5, dash="dot"),
    )
    fig_pareto.add_annotation(
        x=len(pareto_df) - 0.5, y=80, yref="y2",
        text="80% threshold", showarrow=False,
        font=dict(color="#f59e0b", size=10), xanchor="right",
    )
    apply_layout(
        fig_pareto,
        "Barrier Failure Frequency & Cumulative Impact",
        yaxis=dict(title="Failure Count", gridcolor="#21262d"),
        yaxis2=dict(
            title="Cumulative %",
            overlaying="y",
            side="right",
            range=[0, 105],
            ticksuffix="%",
            gridcolor="rgba(0,0,0,0)",
        ),
        barmode="group",
    )
    st.plotly_chart(fig_pareto, width='stretch')

# ===========================================================================
# SECTION 4 – LIFE-SAVING RULE ANALYSIS
# ===========================================================================
st.markdown(
    '<div class="section-header"><h2>⚠️ Life-Saving Rules Analysis</h2>'
    '<p>Rule occurrence frequency and observed SIF-precursor association.</p></div>',
    unsafe_allow_html=True,
)

lsr_col, haz_col = st.columns(2)

with lsr_col:
    lsr_df = get_lsr_analysis_data(df)

    if lsr_df.empty:
        st.info("No Life-Saving Rule data available yet.")
    else:
        lsr_display = lsr_df.head(10).copy()
        lsr_display["Rule_Short"] = lsr_display["Life-Saving Rule"].apply(
            lambda x: x[:28] + "…" if len(x) > 28 else x
        )
        fig_lsr = go.Figure()
        fig_lsr.add_trace(go.Bar(
            x=lsr_display["Count"],
            y=lsr_display["Rule_Short"],
            name="Total Occurrences",
            orientation="h",
            marker_color=PALETTE["blue"],
            hovertemplate="<b>%{y}</b><br>Total: %{x}<extra></extra>",
        ))
        fig_lsr.add_trace(go.Bar(
            x=lsr_display["SIF Precursors"],
            y=lsr_display["Rule_Short"],
            name="SIF Precursors",
            orientation="h",
            marker_color=PALETTE["sif"],
            hovertemplate="<b>%{y}</b><br>SIF Precursors: %{x}<extra></extra>",
        ))
        apply_layout(
            fig_lsr,
            "Life-Saving Rule Occurrence vs SIF Precursor",
            barmode="group",
            xaxis_title="Count",
            height=350,
            yaxis=dict(autorange="reversed", gridcolor="#21262d"),
        )
        st.plotly_chart(fig_lsr, width='stretch')

        # Interactive LSR → associated reports
        st.markdown("**View reports for a specific Life-Saving Rule:**")
        rule_pick = st.selectbox(
            "Select rule",
            ["— choose —"] + lsr_df["Life-Saving Rule"].tolist(),
            key="dash_lsr_pick",
        )
        if rule_pick != "— choose —":
            rule_reports = df[
                df["resolved_life_saving_rules"].apply(lambda r: rule_pick in r)
            ]
            if rule_reports.empty:
                st.info("No reports matched this rule in the current filter.")
            else:
                st.dataframe(
                    rule_reports[["id", "site", "location", "resolved_sif_label", "resolved_priority"]]
                    .rename(columns={"id": "ID", "site": "Site", "location": "Location",
                                     "resolved_sif_label": "SIF Label", "resolved_priority": "Priority"}),
                    width='stretch',
                    hide_index=True,
                )

with haz_col:
    st.markdown("**Hazard / Energy Analysis**")
    haz_data = get_hazard_energy_analysis_data(df)
    dim_opts = {"Hazard": "hazard", "Energy Source": "energy_source", "Exposure": "exposure"}
    haz_choice = st.selectbox("Breakdown dimension", list(dim_opts.keys()), key="dash_haz_dim")
    sel_haz_df = haz_data[dim_opts[haz_choice]]

    if sel_haz_df.empty:
        st.info(f"No {haz_choice} data available in current filter.")
    else:
        top_n = sel_haz_df.head(12)
        dim_col = haz_choice  # column name after rename inside service
        fig_haz = go.Figure()
        fig_haz.add_trace(go.Bar(
            x=top_n[dim_col], y=top_n.get("Non-SIF-potential", [0]*len(top_n)),
            name="Non-SIF",
            marker_color=PALETTE["non_sif"],
        ))
        fig_haz.add_trace(go.Bar(
            x=top_n[dim_col], y=top_n.get("Review Required", [0]*len(top_n)),
            name="Review Required",
            marker_color=PALETTE["review"],
        ))
        fig_haz.add_trace(go.Bar(
            x=top_n[dim_col], y=top_n.get("SIF-potential", [0]*len(top_n)),
            name="SIF-Potential",
            marker_color=PALETTE["sif"],
        ))
        apply_layout(
            fig_haz,
            f"{haz_choice} Breakdown by SIF Classification",
            barmode="stack",
            xaxis_tickangle=-35,
            yaxis_title="Reports",
            height=350,
        )
        st.caption(
            "ℹ️ Observed association in reported data — does not imply statistical causation."
        )
        st.plotly_chart(fig_haz, width='stretch')

# ===========================================================================
# SECTION 5 – SITE SAFETY INTELLIGENCE
# ===========================================================================
st.markdown(
    '<div class="section-header"><h2>🏢 Site Safety Intelligence</h2>'
    '<p>Reported SIF precursor density per site. '
    'Higher reporting may reflect stronger reporting culture, not necessarily higher risk.</p></div>',
    unsafe_allow_html=True,
)

site_df = get_site_safety_intelligence_data(df)

if site_df.empty:
    st.info("No site data available.")
else:
    site_col, heat_col = st.columns([6, 4])

    with site_col:
        st.markdown("**Site Ranking by Reported SIF Precursor Density**")

        # Colour-code density column
        styled = site_df.style.background_gradient(
            subset=["SIF Density (%)"], cmap="YlOrRd", vmin=0, vmax=100
        )

        site_display = site_df.rename(columns={
            "Total Reports":   "Total Obs.",
            "SIF Precursors":  "SIF Events",
            "SIF Density (%)": "SIF Density %",
            "Critical/High":   "Crit/High",
            "Barrier Failures":"Barrier Fails",
            "Immediate Danger":"Imm. Danger",
        })
        st.dataframe(site_display, width='stretch', hide_index=True)

        # Bar chart – site comparison
        fig_site = px.bar(
            site_df,
            x="Site",
            y="SIF Density (%)",
            color="SIF Density (%)",
            color_continuous_scale=["#22c55e", "#f59e0b", "#ef4444"],
            text="SIF Density (%)",
            hover_data=["Total Reports", "SIF Precursors", "Barrier Failures"],
        )
        apply_layout(
            fig_site,
            "Reported SIF Precursor Density by Site (%)",
            yaxis_title="SIF Density (%)",
            coloraxis_showscale=False,
            height=280,
        )
        fig_site.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig_site, width='stretch')

    with heat_col:
        st.markdown("**Risk Co-occurrence Matrix**")
        heat_dim_opts = {"Hazard": "hazard", "Life-Saving Rule": "life_saving_rule"}
        heat_choice = st.selectbox(
            "Site vs", list(heat_dim_opts.keys()), key="dash_heat_dim"
        )
        heatmap_df = get_risk_heatmap_data(df, row_dim="site", col_dim=heat_dim_opts[heat_choice])

        if heatmap_df.empty:
            st.info("Insufficient data to build the co-occurrence matrix.")
        else:
            fig_heat = px.imshow(
                heatmap_df,
                labels=dict(x=heat_choice, y="Site", color="Count"),
                color_continuous_scale="Reds",
                text_auto=True,
                aspect="auto",
            )
            apply_layout(
                fig_heat,
                f"Site × {heat_choice} Co-occurrence",
                height=320,
                xaxis_tickangle=-30,
            )
            fig_heat.update_traces(
                hovertemplate="Site: %{y}<br>" + heat_choice + ": %{x}<br>Count: %{z}<extra></extra>"
            )
            st.plotly_chart(fig_heat, width='stretch')

# ===========================================================================
# SECTION 6 – MANAGEMENT INSIGHTS
# ===========================================================================
st.markdown(
    '<div class="section-header"><h2>💡 Automated Safety Insights</h2>'
    '<p>Generated from actual database values. Updated dynamically as data changes.</p></div>',
    unsafe_allow_html=True,
)

insights = generate_management_insights(df)
for ins in insights:
    st.markdown(
        f'<div class="insight-card">💬 {ins}</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="disclaimer">'
    "ℹ️ <strong>Disclaimer:</strong> Insights reflect reported observations and should support — "
    "not replace — HSE professional judgment."
    "</div>",
    unsafe_allow_html=True,
)
