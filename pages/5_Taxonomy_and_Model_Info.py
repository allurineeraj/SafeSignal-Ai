import streamlit as st
import json
import pandas as pd
import os
import sys

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.model_status import get_model_statuses

st.set_page_config(
    page_title="Taxonomy & Model Info - SIF-Insight",
    page_icon="🧠",
    layout="wide"
)

# Shared CSS for industrial aesthetic
st.markdown("""
<style>
    .safety-alert {
        background-color: #2c0b0e;
        color: #e2818a;
        padding: 1rem;
        border-left: 5px solid #dc3545;
        margin-bottom: 1rem;
        border-radius: 4px;
    }
    .demo-alert {
        background-color: #0c2b3e;
        color: #90c2e7;
        padding: 1rem;
        border-left: 5px solid #17a2b8;
        margin-bottom: 1rem;
        border-radius: 4px;
    }
    .status-card {
        background-color: #1e1e1e;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #4a4a4a;
        margin-bottom: 1rem;
    }
    .status-card.active {
        border-left-color: #28a745;
    }
    .status-card.fallback {
        border-left-color: #ffc107;
    }
    .rule-card {
        background-color: #2b2b2b;
        padding: 1.5rem;
        border-radius: 8px;
        border-top: 3px solid #17a2b8;
        margin-bottom: 1rem;
    }
    .keyword-badge {
        display: inline-block;
        background-color: #444;
        color: #fff;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        margin: 0.2rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 Taxonomy & Model Information")
st.markdown("Overview of the SIF-Insight classification engine, active models, and internal taxonomies.")

st.markdown("""
<div class="safety-alert">
    <strong>⚠️ IMPORTANT:</strong> AI results are preliminary and require HSE validation. 
</div>
<div class="demo-alert">
    <strong>ℹ️ SYSTEM NOTICE:</strong> Demonstration dataset only. Production deployment requires OIL-approved historical data, taxonomy and HSE-validated labels.
</div>
""", unsafe_allow_html=True)


# --- 1. MODEL STATUS SECTION ---
st.header("1. Active Services & Fallback Status", divider="gray")
st.markdown("SIF-Insight uses a localized, privacy-first architecture. If heavy AI models (like Whisper or IndicTrans2) are unavailable in the current environment, the system gracefully degrades to safe fallback modes without relying on external cloud APIs.")

statuses = get_model_statuses()

cols = st.columns(3)
for idx, (service, info) in enumerate(statuses.items()):
    with cols[idx % 3]:
        css_class = "active" if info["status"] else "fallback"
        icon = "✅" if info["status"] else "⚠️"
        st.markdown(f"""
        <div class="status-card {css_class}">
            <h4 style="margin-top:0;">{icon} {service}</h4>
            <p style="margin-bottom:0; color:#aaa; font-size:0.9rem;">{info['label']}</p>
        </div>
        """, unsafe_allow_html=True)


# --- 2. SIF CLASSIFICATION LOGIC ---
st.header("2. SIF Classification Engine Architecture", divider="gray")
st.markdown("""
The SIF-Insight classification engine uses a **3-Layer Hybrid Pipeline** to evaluate reports:

### Layer 1: Rule-Based Safety Engine
Extracts text matching specific phrases/concepts from the IOGP Life-Saving Rules taxonomy. 
- **Negation Handling:** Evaluates context within a short text window. Phrases like `"no gas testing done"` trigger a barrier failure, whereas `"gas testing completed"` does not.

### Layer 2: Explainable Scoring
Assigns risk points based on the extracted triggers:
* **+3 pts:** Person directly exposed (e.g., entered confined space, working at height)
* **+3 pts:** Barrier missing or failed (e.g., no permit, isolation failed)
* **+2 pts:** High-energy hazard (e.g., electricity, pressure, crane)
* **+2 pts:** Credible fatal consequence (e.g., crushing, electrocution)
* **+1 pt:** Multiple people exposed
* **+1 pt:** Near-miss context

**Score Thresholds:**
* `0 - 3`: **Non-SIF-potential**
* `4 - 6`: **Review Required**
* `7+`: **SIF-potential**

### Layer 3: Machine Learning Model (Optional)
If a local `LogisticRegression` model trained on `TfidfVectorizer` data is available, it calculates probability/confidence scores. Otherwise, the system relies strictly on the highly deterministic **Rule-engine fallback mode**.
""")


# --- 3. LIFE-SAVING RULES TAXONOMY ---
st.header("3. IOGP Life-Saving Rules Taxonomy", divider="gray")
st.markdown("The system maps report text to the following predefined categories and keywords.")

@st.cache_data
def load_taxonomy():
    filepath = os.path.join(project_root, "data", "life_saving_rules.json")
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

rules = load_taxonomy()

if not rules:
    st.warning("Life-Saving Rules taxonomy file not found in `data/` directory.")
else:
    for rule in rules:
        st.markdown(f"""
        <div class="rule-card">
            <h3 style="margin-top:0; color:#17a2b8;">{rule['rule_name']}</h3>
            <p><em>{rule['description']}</em></p>
            
            <strong>Extraction Keywords:</strong><br>
            {''.join([f'<span class="keyword-badge">{kw}</span>' for kw in rule['keywords']])}
            <br><br>
            
            <div style="display: flex; gap: 2rem;">
                <div style="flex: 1;">
                    <strong>Typical Hazards:</strong>
                    <ul>
                        {''.join([f'<li>{hz}</li>' for hz in rule['typical_hazards']])}
                    </ul>
                </div>
                <div style="flex: 1;">
                    <strong>Typical Failed Barriers:</strong>
                    <ul>
                        {''.join([f'<li>{fb}</li>' for fb in rule['typical_failed_barriers']])}
                    </ul>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
