import streamlit as st
import os
from database.db import get_stats, init_db
from services.model_status import get_model_statuses

st.set_page_config(
    page_title="SIF-Insight - OIL Safety Intelligence",
    page_icon="🛡️",
    layout="wide"
)

# Initialize database
init_db()

# Role Selector in Sidebar (Global Hackathon Demo Selector)
st.sidebar.markdown("### 🛠️ DEMO CONTROLS")
if "user_role" not in st.session_state:
    st.session_state.user_role = "HSE Officer"

user_role = st.sidebar.selectbox(
    "Active User Role (Demo Mode)",
    ["Worker / Observer", "Supervisor", "HSE Officer", "HSE Manager", "Administrator"],
    index=2
)
st.session_state.user_role = user_role

st.sidebar.info(
    f"Currently acting as: **{st.session_state.user_role}**\n\n"
    "Change role to simulate different workflow pages and interface action controls."
)

# Model Status Dashboard Widget
st.sidebar.markdown("### ⚙️ SYSTEM STATUS")
statuses = get_model_statuses()
for name, info in statuses.items():
    icon = "✓" if info["status"] else "⚠️"
    st.sidebar.markdown(f"**{name}**: {icon} `{info['label']}`")

# Header & Branding
st.title("🛡️ SIF-Insight")
st.subheader("“Find serious dangers early—before they become serious injuries or fatalities.”")

st.markdown(
    "SIF-Insight is a decision-support safety intelligence platform designed for **Oil India Limited (OIL)** "
    "(Smart India Hackathon Problem Statement 26165). The platform processes unstructured text and files to identify "
    "high-risk precursors (Serious Injury and Fatality potentials) before incidents escalate."
)

st.warning(
    "⚠️ **DEMONSTRATION & COMPLIANCE NOTICE**\n\n"
    "AI results are preliminary and require HSE validation. "
    "Demonstration dataset only. Production deployment requires OIL-approved historical data, taxonomy, and HSE-validated labels."
)

st.markdown("---")

# Global KPIs section
st.markdown("### 📊 Platform Metrics Summary")
try:
    stats = get_stats()
except Exception as e:
    stats = {
        'total_reports': 0, 'sif_count': 0, 'non_sif_count': 0,
        'review_req_count': 0, 'critical_count': 0, 'closed_count': 0,
        'open_actions_count': 0, 'sif_percentage': 0.0,
        'highest_risk_site': 'None', 'most_freq_rule': 'None', 'most_freq_barrier': 'None'
    }

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Observation Reports", stats['total_reports'])
with c2:
    st.metric("SIF-potential Flagged", stats['sif_count'])
with c3:
    st.metric("Review Required", stats['review_req_count'])
with c4:
    st.metric("SIF Precursor Density", f"{stats['sif_percentage']}%", help="SIF reports per 100 submitted reports")

st.markdown("### 📍 Operational Insights")
c5, c6, c7 = st.columns(3)
with c5:
    st.info(f"**Highest Risk Site**: {stats['highest_risk_site']}\n\n*Site rankings may be affected by reporting culture, workforce size, activity level and available data.*")
with c6:
    st.info(f"**Top Broken Barrier**: {stats['most_freq_barrier']}")
with c7:
    st.info(f"**Top Life-Saving Rule**: {stats['most_freq_rule']}")
