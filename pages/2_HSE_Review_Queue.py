import streamlit as st
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="HSE Review Queue",
    page_icon="📁",
    layout="wide",
)


# ============================================================
# DATABASE DISCOVERY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


def find_database():
    """
    Find the SQLite database containing the SafeSignalAI reports table.
    This avoids hard-coding an unknown database filename.
    """

    possible_names = [
        "sif_insight.db",
        "sif_insight.sqlite",
        "sif_insight.sqlite3",
        "safesignal.db",
        "safesignal.sqlite",
        "database.db",
        "app.db",
        "data.db",
    ]

    search_dirs = [
        BASE_DIR,
        BASE_DIR / "database",
        BASE_DIR / "data",
    ]

    # First try common database names.
    for directory in search_dirs:
        if directory.exists():
            for name in possible_names:
                path = directory / name
                if path.exists():
                    try:
                        conn = sqlite3.connect(path)
                        tables = conn.execute(
                            "SELECT name FROM sqlite_master "
                            "WHERE type='table'"
                        ).fetchall()
                        conn.close()

                        table_names = {x[0] for x in tables}

                        if "reports" in table_names:
                            return path
                    except Exception:
                        pass

    # Then search all sqlite/db files.
    for pattern in ["*.db", "*.sqlite", "*.sqlite3"]:
        for path in BASE_DIR.rglob(pattern):

            # Don't accidentally inspect virtual environments.
            if ".venv" in path.parts or "venv" in path.parts:
                continue

            try:
                conn = sqlite3.connect(path)
                tables = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table'"
                ).fetchall()
                conn.close()

                table_names = {x[0] for x in tables}

                if "reports" in table_names:
                    return path

            except Exception:
                continue

    return None


DB_PATH = find_database()


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    if DB_PATH is None:
        return None

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table_name):
    result = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    ).fetchone()

    return result is not None


def get_table_columns(conn, table_name):
    if not table_exists(conn, table_name):
        return []

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [row["name"] for row in rows]


def safe_value(row, key, default="—"):
    """
    Safely retrieve a database value.

    IMPORTANT:
    We use .get()-style logic here instead of assuming every
    report contains reporter_name.
    """

    if row is None:
        return default

    try:
        value = row[key]
    except (KeyError, IndexError):
        return default

    if value is None or value == "":
        return default

    return value


def parse_json_list(value):
    if not value:
        return []

    if isinstance(value, list):
        return value

    try:
        result = json.loads(value)

        if isinstance(result, list):
            return result

        return [str(result)]

    except Exception:
        return [str(value)]


# ============================================================
# ROLE
# ============================================================

if "active_role" not in st.session_state:
    st.session_state["active_role"] = "Worker / Observer"

ROLE_OPTIONS = [
    "Worker / Observer",
    "Supervisor",
    "HSE Officer",
    "HSE Manager",
    "Administrator",
]

with st.sidebar:

    st.markdown("### 🛠️ DEMO CONTROLS")

    active_role = st.selectbox(
        "Active User Role (Demo Mode)",
        ROLE_OPTIONS,
        index=ROLE_OPTIONS.index(
            st.session_state.get(
                "active_role",
                "Worker / Observer"
            )
        ),
    )

    st.session_state["active_role"] = active_role


# ============================================================
# PERMISSIONS & AUTHENTICATION
# ============================================================

from database.db import verify_credentials

REVIEW_ROLES = {
    "HSE Officer",
    "HSE Manager",
}

ACTION_ROLES = {
    "HSE Officer",
    "HSE Manager",
}

if active_role not in REVIEW_ROLES:
    st.error(
        "🔒 HSE Review Queue is available only to HSE Officer "
        "and HSE Manager roles."
    )
    st.info(
        "Use the Demo Controls in the sidebar and select "
        "'HSE Officer' to review reports."
    )
    st.stop()

# Actual Authentication
if "authenticated_user" not in st.session_state:
    st.session_state["authenticated_user"] = None

if not st.session_state["authenticated_user"]:
    st.markdown("### 🔒 HSE Officer Login Required")
    st.info("You must authenticate to access the HSE Review Queue.")
    
    with st.form("login_form"):
        user_id = st.text_input("Officer ID", placeholder="e.g. HSE001")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Login", type="primary")
        
        if submitted:
            user = verify_credentials(user_id, password)
            if user:
                # Ensure the authenticated user role matches the selected role (or at least is a REVIEW_ROLE)
                if user["role"] not in REVIEW_ROLES:
                    st.error("Access Denied: Your account does not have HSE Review privileges.")
                else:
                    st.session_state["authenticated_user"] = user
                    st.success(f"Welcome back, {user['user_id']}!")
                    st.rerun()
            else:
                st.error("❌ Invalid credentials. Please try again.")
    st.stop()
else:
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"**Authenticated as:** {st.session_state['authenticated_user']['user_id']}")
        if st.button("Logout"):
            st.session_state["authenticated_user"] = None
            st.rerun()


# ============================================================
# DATABASE CHECK
# ============================================================

if DB_PATH is None:

    st.error(
        "❌ SafeSignalAI SQLite database could not be found."
    )

    st.write(
        "Expected a SQLite database containing a `reports` table."
    )

    st.stop()


conn = get_connection()

if conn is None:
    st.error("❌ Could not connect to the SafeSignalAI database.")
    st.stop()


# ============================================================
# PAGE HEADER
# ============================================================

st.title("📁 HSE Review Queue")

st.subheader(
    "Manage, classify, and audit OIL safety observation submissions."
)


# ============================================================
# LOAD REPORTS
# ============================================================

report_columns = get_table_columns(conn, "reports")

if not report_columns:

    st.error(
        "❌ The database contains no usable `reports` table."
    )

    conn.close()
    st.stop()


# ============================================================
# FILTER CONTROLS
# ============================================================

st.markdown("## 🔎 Filter Queue Controls")

with st.expander("Expand Filter Controls", expanded=True):

    col1, col2, col3 = st.columns(3)

    # --------------------------------------------------------
    # Priority
    # --------------------------------------------------------

    with col1:

        priority_options = [
            "All",
            "Critical",
            "High",
            "Medium",
            "Low",
        ]

        priority_filter = st.selectbox(
            "Priority Status",
            priority_options,
        )

    # --------------------------------------------------------
    # Site
    # --------------------------------------------------------

    with col2:

        sites_query = """
            SELECT DISTINCT site
            FROM reports
            WHERE site IS NOT NULL
            ORDER BY site
        """

        sites = [
            row["site"]
            for row in conn.execute(sites_query).fetchall()
            if row["site"]
        ]

        site_options = ["All"] + sites

        site_filter = st.selectbox(
            "Site / Facility",
            site_options,
        )

    # --------------------------------------------------------
    # Workflow Status
    # --------------------------------------------------------

    with col3:

        status_options = [
            "All",
            "Pending HSE Review",
            "Accepted",
            "Corrected",
            "Rejected",
            "Duplicate",
            "Action Assigned",
            "Action In Progress",
            "Closed",
        ]

        status_filter = st.selectbox(
            "Workflow Status",
            status_options,
            index=1,
        )

    col4, col5, col6 = st.columns(3)

    # --------------------------------------------------------
    # SIF
    # --------------------------------------------------------

    with col4:

        sif_filter = st.selectbox(
            "SIF Label",
            [
                "All",
                "SIF-potential",
                "Review Required",
                "Non-SIF-potential",
            ],
        )

    # --------------------------------------------------------
    # Report Type
    # --------------------------------------------------------

    with col5:

        type_rows = conn.execute(
            """
            SELECT DISTINCT report_type
            FROM reports
            WHERE report_type IS NOT NULL
            ORDER BY report_type
            """
        ).fetchall()

        type_options = ["All"] + [
            row["report_type"]
            for row in type_rows
            if row["report_type"]
        ]

        type_filter = st.selectbox(
            "Report Type",
            type_options,
        )

    # --------------------------------------------------------
    # Life Saving Rule
    # --------------------------------------------------------

    with col6:

        lsr_filter = st.selectbox(
            "Life-Saving Rule Triggered",
            [
                "All",
                "Yes",
                "No",
            ],
        )

    # --------------------------------------------------------
    # Immediate danger
    # --------------------------------------------------------

    danger_filter = st.radio(
        "Immediate Danger Filter",
        [
            "All",
            "YES",
            "NO",
        ],
        horizontal=True,
    )


# ============================================================
# BUILD QUERY
# ============================================================

query = """
SELECT
    r.*
FROM reports r
"""

params = []

conditions = []


# ------------------------------------------------------------
# SIF JOIN
# ------------------------------------------------------------

if table_exists(conn, "ai_predictions"):

    query = """
    SELECT
        r.*,
        a.sif_label AS ai_sif_label,
        a.sif_score AS ai_sif_score,
        a.confidence AS ai_confidence,
        a.priority AS ai_priority,
        a.activity AS ai_activity,
        a.hazard AS ai_hazard,
        a.energy_source AS ai_energy_source,
        a.exposure AS ai_exposure,
        a.failed_barrier AS ai_failed_barrier,
        a.potential_consequence AS ai_potential_consequence,
        a.life_saving_rules AS ai_life_saving_rules,
        a.evidence_phrases AS ai_evidence_phrases,
        a.classifier_mode AS ai_classifier_mode,
        a.model_version AS ai_model_version,
        a.llm_provider AS ai_llm_provider,
        a.llm_model AS ai_llm_model,
        a.llm_analysis_status AS ai_llm_analysis_status,
        a.llm_confidence AS ai_llm_confidence,
        a.actual_injury AS ai_actual_injury,
        a.explanation AS ai_explanation
    FROM reports r
    LEFT JOIN ai_predictions a
        ON r.id = a.report_id
    """

    sif_column = "a.sif_label"

else:

    sif_column = "NULL"


# ------------------------------------------------------------
# Priority
# ------------------------------------------------------------

if priority_filter != "All":

    conditions.append(
        "r.review_priority = ?"
    )

    params.append(priority_filter)


# ------------------------------------------------------------
# Site
# ------------------------------------------------------------

if site_filter != "All":

    conditions.append(
        "r.site = ?"
    )

    params.append(site_filter)


# ------------------------------------------------------------
# Status
# ------------------------------------------------------------

if status_filter != "All":

    conditions.append(
        "r.report_status = ?"
    )

    params.append(status_filter)


# ------------------------------------------------------------
# SIF
# ------------------------------------------------------------

if sif_filter != "All":

    conditions.append(
        f"{sif_column} = ?"
    )

    params.append(sif_filter)


# ------------------------------------------------------------
# Report Type
# ------------------------------------------------------------

if type_filter != "All":

    conditions.append(
        "r.report_type = ?"
    )

    params.append(type_filter)


# ------------------------------------------------------------
# Immediate Danger
# ------------------------------------------------------------

if danger_filter == "YES":

    conditions.append(
        "COALESCE(r.immediate_danger, 0) = 1"
    )

elif danger_filter == "NO":

    conditions.append(
        "COALESCE(r.immediate_danger, 0) = 0"
    )


# ------------------------------------------------------------
# Life Saving Rule
# ------------------------------------------------------------

if lsr_filter == "Yes":

    if table_exists(conn, "ai_predictions"):

        conditions.append(
            """
            a.life_saving_rules IS NOT NULL
            AND a.life_saving_rules != ''
            AND a.life_saving_rules != '[]'
            """
        )

elif lsr_filter == "No":

    if table_exists(conn, "ai_predictions"):

        conditions.append(
            """
            (
                a.life_saving_rules IS NULL
                OR a.life_saving_rules = ''
                OR a.life_saving_rules = '[]'
            )
            """
        )


# ------------------------------------------------------------
# WHERE
# ------------------------------------------------------------

if conditions:

    query += " WHERE " + " AND ".join(conditions)


# ------------------------------------------------------------
# ORDER
# ------------------------------------------------------------

query += """
ORDER BY
    CASE r.review_priority
        WHEN 'Critical' THEN 1
        WHEN 'High' THEN 2
        WHEN 'Medium' THEN 3
        WHEN 'Low' THEN 4
        ELSE 5
    END,
    datetime(r.created_at) DESC
"""


reports = conn.execute(
    query,
    params,
).fetchall()


# ============================================================
# QUEUE SUMMARY
# ============================================================

st.write(
    f"**Showing {len(reports)} reports.**"
)


# ============================================================
# REPORT TABLE
# ============================================================

if reports:

    table_data = []

    for report in reports:

        table_data.append(
            {
                "ID": f"#{safe_value(report, 'id', '')}",
                "Date": safe_value(
                    report,
                    "created_at",
                ),
                "Site": safe_value(
                    report,
                    "site",
                ),
                "Type": safe_value(
                    report,
                    "report_type",
                ),
                "SIF Assessment": safe_value(
                    report,
                    "ai_sif_label",
                    "—",
                ),
                "Priority": safe_value(
                    report,
                    "review_priority",
                ),
                "Danger": (
                    "YES"
                    if safe_value(
                        report,
                        "immediate_danger",
                        0,
                    )
                    in [1, "1", True]
                    else "NO"
                ),
                "Status": safe_value(
                    report,
                    "report_status",
                ),
            }
        )

    st.dataframe(
        table_data,
        width='stretch',
        hide_index=True,
    )

else:

    st.info(
        "No reports match the selected filters."
    )


# ============================================================
# HSE DETAIL VIEW
# ============================================================

st.divider()

st.markdown(
    "## 🔎 HSE Detail View & Action Review Panel"
)


# ============================================================
# REPORT SELECTOR
# ============================================================

if reports:

    report_options = {}

    for report in reports:

        report_id = safe_value(
            report,
            "id",
            "",
        )

        report_options[
            f"#{report_id} - "
            f"{safe_value(report, 'site')} "
            f"({safe_value(report, 'report_status')})"
        ] = report_id

    selected_label = st.selectbox(
        "Select Report ID to Review",
        list(report_options.keys()),
    )

    selected_id = report_options[selected_label]

else:

    selected_id = None


# ============================================================
# LOAD SELECTED REPORT
# ============================================================

if selected_id is None:

    st.info("Select a report to review.")

    conn.close()
    st.stop()


detail_query = """
SELECT
    r.*
"""

if table_exists(conn, "ai_predictions"):

    detail_query += """
        ,
        a.sif_label AS ai_sif_label,
        a.sif_score AS ai_sif_score,
        a.confidence AS ai_confidence,
        a.priority AS ai_priority,
        a.activity AS ai_activity,
        a.hazard AS ai_hazard,
        a.energy_source AS ai_energy_source,
        a.exposure AS ai_exposure,
        a.failed_barrier AS ai_failed_barrier,
        a.potential_consequence AS ai_potential_consequence,
        a.life_saving_rules AS ai_life_saving_rules,
        a.evidence_phrases AS ai_evidence_phrases,
        a.classifier_mode AS ai_classifier_mode,
        a.model_version AS ai_model_version,
        a.llm_provider AS ai_llm_provider,
        a.llm_model AS ai_llm_model,
        a.llm_analysis_status AS ai_llm_analysis_status,
        a.llm_confidence AS ai_llm_confidence,
        a.actual_injury AS ai_actual_injury,
        a.explanation AS ai_explanation
    """

detail_query += """
FROM reports r
"""

if table_exists(conn, "ai_predictions"):

    detail_query += """
    LEFT JOIN ai_predictions a
        ON r.id = a.report_id
    """

detail_query += """
WHERE r.id = ?
"""


report = conn.execute(
    detail_query,
    (selected_id,),
).fetchone()


if report is None:

    st.error(
        "Selected report could not be loaded."
    )

    conn.close()
    st.stop()


# ============================================================
# 1. SAFETY OBSERVATION REPORT INFO
# ============================================================

st.markdown(
    "### 1. Safety Observation Report Info"
)


info_col1, info_col2, info_col3 = st.columns(3)


with info_col1:

    st.markdown(
        f"""
**Report ID:** #{safe_value(report, 'id')}

**Type:** {safe_value(report, 'report_type')}

**Site:** {safe_value(report, 'site')}

**Location:** {safe_value(report, 'location')}
"""
    )


with info_col2:

    # IMPORTANT:
    # Database schema uses submitted_by.
    # We intentionally DO NOT use reporter_name.
    submitted_by = safe_value(
        report,
        "submitted_by",
        "Not provided",
    )

    anonymous = safe_value(
        report,
        "anonymous",
        0,
    )

    if anonymous in [1, "1", True]:
        submitted_display = "Anonymous"
    else:
        submitted_display = submitted_by

    st.markdown(
        f"""
**Submitted By:** {submitted_display}

**Original Language:** {safe_value(report, 'original_language')}

**Source:** {safe_value(report, 'source_type')}

**Submitted On Behalf:** {
    'Yes'
    if safe_value(report, 'submitted_on_behalf', 0)
    in [1, '1', True]
    else 'No'
}
"""
    )


with info_col3:

    danger = (
        "YES"
        if safe_value(
            report,
            "immediate_danger",
            0,
        )
        in [1, "1", True]
        else "NO"
    )

    st.markdown(
        f"""
**Immediate Danger:** {danger}

**Priority:** {safe_value(report, 'review_priority')}

**Status:** {safe_value(report, 'report_status')}

**Created:** {safe_value(report, 'created_at')}
"""
    )


# ============================================================
# ORIGINAL REPORT
# ============================================================

st.markdown("#### Original Observation")

original_text = safe_value(
    report,
    "original_text",
    "No observation text available.",
)

st.info(original_text)


# ============================================================
# TRANSLATED TEXT
# ============================================================

translated_text = safe_value(
    report,
    "translated_text",
    "",
)

if translated_text != "—":

    st.markdown("#### Translated / Normalized Text")

    st.write(translated_text)


# ============================================================
# IMMEDIATE ACTION
# ============================================================

immediate_action = safe_value(
    report,
    "immediate_action",
    "",
)

if immediate_action != "—":

    st.markdown("#### Immediate Action Taken")

    st.write(immediate_action)


# ============================================================
# 2. AI ASSESSMENT
# ============================================================

st.divider()

st.markdown(
    "### 2. AI Safety Assessment"
)


ai_col1, ai_col2, ai_col3 = st.columns(3)


with ai_col1:

    st.metric(
        "SIF Assessment",
        safe_value(
            report,
            "ai_sif_label",
            "Unavailable",
        ),
    )


with ai_col2:

    score = safe_value(
        report,
        "ai_sif_score",
        "—",
    )

    st.metric(
        "SIF Score",
        score,
    )


with ai_col3:

    confidence = safe_value(
        report,
        "ai_confidence",
        "—",
    )

    if isinstance(confidence, (float, int)):

        confidence_display = (
            f"{confidence * 100:.1f}%"
            if confidence <= 1
            else f"{confidence:.1f}%"
        )

    else:

        confidence_display = str(confidence)

    st.metric(
        "ML Confidence",
        confidence_display,
    )


# ============================================================
# AI DETAILS
# ============================================================

ai_details_col1, ai_details_col2 = st.columns(2)


with ai_details_col1:

    st.markdown("#### Risk Analysis")

    st.write(
        f"**Activity:** "
        f"{safe_value(report, 'ai_activity')}"

    )

    st.write(
        f"**Hazard:** "
        f"{safe_value(report, 'ai_hazard')}"
    )

    st.write(
        f"**Energy Source:** "
        f"{safe_value(report, 'ai_energy_source')}"
    )

    st.write(
        f"**Exposure:** "
        f"{safe_value(report, 'ai_exposure')}"
    )


with ai_details_col2:

    st.markdown("#### Barrier / Consequence")

    st.write(
        f"**Failed Barrier:** "
        f"{safe_value(report, 'ai_failed_barrier')}"
    )

    st.write(
        f"**Potential Consequence:** "
        f"{safe_value(report, 'ai_potential_consequence')}"
    )

    st.write(
        f"**Actual Injury:** "
        f"{safe_value(report, 'ai_actual_injury', 'Not identified from report')}"
    )

    with st.expander("🤖 AI Engine Metadata"):
        st.write(
            f"**LLM Provider:** "
            f"{safe_value(report, 'ai_llm_provider', 'N/A')}"
        )
        st.write(
            f"**LLM Model:** "
            f"{safe_value(report, 'ai_llm_model', 'N/A')}"
        )
        st.write(
            f"**Analysis Status:** "
            f"{safe_value(report, 'ai_llm_analysis_status', 'N/A')}"
        )
        st.write(
            f"**LLM Confidence:** "
            f"{safe_value(report, 'ai_llm_confidence', 'N/A')}"
        )
        st.write(
            f"**Classifier Mode:** "
            f"{safe_value(report, 'ai_classifier_mode')}"
        )
        st.write(
            f"**Model Version:** "
            f"{safe_value(report, 'ai_model_version')}"
        )


# ============================================================
# LIFE-SAVING RULES
# ============================================================

lsr_values = parse_json_list(
    safe_value(
        report,
        "ai_life_saving_rules",
        "",
    )
)

st.markdown("#### Life-Saving Rules Triggered")

if lsr_values:

    for rule in lsr_values:

        st.success(
            f"🛡️ {rule}"
        )

else:

    st.info(
        "No Life-Saving Rule triggered."
    )


# ============================================================
# EVIDENCE PHRASES & REASONING
# ============================================================

evidence_values = parse_json_list(
    safe_value(
        report,
        "ai_evidence_phrases",
        "",
    )
)

if evidence_values:

    st.markdown("#### Detected Evidence")

    for evidence in evidence_values:

        st.write(
            f"• {evidence}"
        )

ai_explanation = safe_value(report, "ai_explanation", "")
if ai_explanation and ai_explanation != "—":
    st.markdown("#### AI Reasoning & Summary")
    st.code(ai_explanation, language="markdown")

# ============================================================
# 3. HSE REVIEW
# ============================================================

st.divider()

st.markdown(
    "### 3. HSE Validation / Correction"
)


existing_review = None


if table_exists(conn, "hse_reviews"):

    existing_review = conn.execute(
        """
        SELECT *
        FROM hse_reviews
        WHERE report_id = ?
        """,
        (selected_id,),
    ).fetchone()


if existing_review:

    st.info(
        f"Existing HSE review: "
        f"{safe_value(existing_review, 'review_status')}"
    )

    st.write(
        f"**Reviewer:** "
        f"{safe_value(existing_review, 'reviewer_name')}"
    )

    st.write(
        f"**Reviewed At:** "
        f"{safe_value(existing_review, 'reviewed_at')}"
    )


# ============================================================
# ONLY PENDING REPORTS CAN BE REVIEWED
# ============================================================

current_status = safe_value(
    report,
    "report_status",
    "",
)


reviewable = current_status == "Pending HSE Review"


if not reviewable:

    st.warning(
        f"This report is currently **{current_status}**. "
        "HSE review controls are disabled."
    )


# ============================================================
# HSE INPUTS
# ============================================================

current_sif = safe_value(
    report,
    "ai_sif_label",
    "Review Required",
)

current_priority = safe_value(
    report,
    "review_priority",
    "Medium",
)

current_activity = safe_value(
    report,
    "ai_activity",
    "",
)

current_hazard = safe_value(
    report,
    "ai_hazard",
    "",
)

current_energy = safe_value(
    report,
    "ai_energy_source",
    "",
)

current_exposure = safe_value(
    report,
    "ai_exposure",
    "",
)

current_barrier = safe_value(
    report,
    "ai_failed_barrier",
    "",
)

current_consequence = safe_value(
    report,
    "ai_potential_consequence",
    "",
)

current_actual_injury = safe_value(
    report,
    "ai_actual_injury",
    "",
)



if reviewable:

    hse1, hse2 = st.columns(2)

    with hse1:

        final_sif = st.selectbox(
            "Final SIF Classification",
            [
                "SIF-potential",
                "Review Required",
                "Non-SIF-potential",
            ],
            index=(
                [
                    "SIF-potential",
                    "Review Required",
                    "Non-SIF-potential",
                ].index(current_sif)
                if current_sif
                in [
                    "SIF-potential",
                    "Review Required",
                    "Non-SIF-potential",
                ]
                else 1
            ),
        )

        final_priority = st.selectbox(
            "Final Priority",
            [
                "Critical",
                "High",
                "Medium",
                "Low",
            ],
            index=(
                [
                    "Critical",
                    "High",
                    "Medium",
                    "Low",
                ].index(current_priority)
                if current_priority
                in [
                    "Critical",
                    "High",
                    "Medium",
                    "Low",
                ]
                else 2
            ),
        )

        final_activity = st.text_input(
            "Activity",
            value=(
                ""
                if current_activity == "—"
                else str(current_activity)
            ),
        )

        final_hazard = st.text_input(
            "Hazard",
            value=(
                ""
                if current_hazard == "—"
                else str(current_hazard)
            ),
        )

        final_energy = st.text_input(
            "Energy Source",
            value=(
                ""
                if current_energy == "—"
                else str(current_energy)
            ),
        )


    with hse2:

        final_exposure = st.text_input(
            "Exposure",
            value=(
                ""
                if current_exposure == "—"
                else str(current_exposure)
            ),
        )

        final_barrier = st.text_input(
            "Failed Barrier",
            value=(
                ""
                if current_barrier == "—"
                else str(current_barrier)
            ),
        )

        final_consequence = st.text_area(
            "Potential Consequence",
            value=(
                ""
                if current_consequence == "—"
                else str(current_consequence)
            ),
        )

        final_actual_injury = st.text_area(
            "Actual Injury",
            value=(
                ""
                if current_actual_injury == "—"
                else str(current_actual_injury)
            ),
        )

        hse_comments = st.text_area(
            "HSE Comments",
            placeholder=(
                "Enter validation comments or correction reason..."
            ),
        )


    # ========================================================
    # REVIEW ACTION
    # ========================================================

    st.markdown("#### HSE Decision")

    decision = st.radio(
        "Select action",
        [
            "Accept AI Result",
            "Correct AI Result",
            "Reject Report",
            "Mark as Duplicate",
        ],
        horizontal=True,
    )


    # ========================================================
    # SUBMIT REVIEW
    # ========================================================

    if st.button(
        "💾 Submit HSE Review",
        type="primary",
        width='stretch',
    ):

        reviewer_name = (
            "HSE Officer"
            if active_role == "HSE Officer"
            else "HSE Manager"
        )


        if decision == "Accept AI Result":

            review_status = "Accepted"

        elif decision == "Correct AI Result":

            review_status = "Corrected"

        elif decision == "Reject Report":

            review_status = "Rejected"

        else:

            review_status = "Duplicate"


        # ----------------------------------------------------
        # Determine next workflow state
        # ----------------------------------------------------

        next_status = review_status


        # ----------------------------------------------------
        # Save review
        # ----------------------------------------------------

        try:

            review_columns = get_table_columns(
                conn,
                "hse_reviews",
            )


            if not review_columns:

                st.error(
                    "The hse_reviews table does not exist."
                )

            else:

                life_saving_rules_json = json.dumps(
                    lsr_values
                )


                if existing_review:

                    conn.execute(
                        """
                        UPDATE hse_reviews
                        SET
                            reviewer_name = ?,
                            final_sif_label = ?,
                            final_priority = ?,
                            final_activity = ?,
                            final_hazard = ?,
                            final_energy_source = ?,
                            final_exposure = ?,
                            final_failed_barrier = ?,
                            final_potential_consequence = ?,
                            final_life_saving_rules = ?,
                            final_actual_injury = ?,
                            hse_comments = ?,
                            review_status = ?,
                            reviewed_at = CURRENT_TIMESTAMP
                        WHERE report_id = ?
                        """,
                        (
                            reviewer_name,
                            final_sif,
                            final_priority,
                            final_activity,
                            final_hazard,
                            final_energy,
                            final_exposure,
                            final_barrier,
                            final_consequence,
                            life_saving_rules_json,
                            final_actual_injury,
                            hse_comments,
                            review_status,
                            selected_id,
                        ),
                    )

                else:

                    conn.execute(
                        """
                        INSERT INTO hse_reviews (
                            report_id,
                            reviewer_name,
                            final_sif_label,
                            final_priority,
                            final_activity,
                            final_hazard,
                            final_energy_source,
                            final_exposure,
                            final_failed_barrier,
                            final_potential_consequence,
                            final_life_saving_rules,
                            final_actual_injury,
                            hse_comments,
                            review_status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            selected_id,
                            reviewer_name,
                            final_sif,
                            final_priority,
                            final_activity,
                            final_hazard,
                            final_energy,
                            final_exposure,
                            final_barrier,
                            final_consequence,
                            life_saving_rules_json,
                            final_actual_injury,
                            hse_comments,
                            review_status,
                        ),
                    )


                # ------------------------------------------------
                # Update report status
                # ------------------------------------------------

                old_status = current_status

                conn.execute(
                    """
                    UPDATE reports
                    SET
                        report_status = ?,
                        review_priority = ?
                    WHERE id = ?
                    """,
                    (
                        next_status,
                        final_priority,
                        selected_id,
                    ),
                )


                # ------------------------------------------------
                # Audit log
                # ------------------------------------------------

                if table_exists(
                    conn,
                    "audit_log",
                ):

                    conn.execute(
                        """
                        INSERT INTO audit_log (
                            report_id,
                            user_name,
                            role,
                            action,
                            field_name,
                            old_value,
                            new_value
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            selected_id,
                            reviewer_name,
                            active_role,
                            "Update Status",
                            "report_status",
                            old_status,
                            next_status,
                        ),
                    )


                    conn.execute(
                        """
                        INSERT INTO audit_log (
                            report_id,
                            user_name,
                            role,
                            action,
                            field_name,
                            old_value,
                            new_value
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            selected_id,
                            reviewer_name,
                            active_role,
                            "Update Field",
                            "sif_label",
                            current_sif,
                            final_sif,
                        ),
                    )


                conn.commit()


                st.success(
                    f"✅ Report #{selected_id} "
                    f"has been marked as **{next_status}**."
                )

                st.info(
                    "The original AI prediction is preserved. "
                    "The HSE decision is stored separately."
                )

                st.rerun()


        except Exception as e:

            conn.rollback()

            st.error(
                "❌ Could not save the HSE review."
            )

            st.exception(e)


# ============================================================
# 4. CORRECTIVE ACTIONS
# ============================================================

st.divider()

st.markdown(
    "### 4. Corrective Action"
)


can_assign_action = (
    active_role in ACTION_ROLES
    and current_status in [
        "Accepted",
        "Corrected",
        "Action Assigned",
        "Action In Progress",
    ]
)


if not table_exists(
    conn,
    "corrective_actions",
):

    st.info(
        "Corrective action table is not available."
    )

elif can_assign_action:

    existing_actions = conn.execute(
        """
        SELECT *
        FROM corrective_actions
        WHERE report_id = ?
        ORDER BY datetime(assigned_at) DESC
        """,
        (selected_id,),
    ).fetchall()


    if existing_actions:

        st.markdown(
            "#### Existing Corrective Actions"
        )

        for action in existing_actions:

            with st.container(border=True):

                st.write(
                    f"**Action:** "
                    f"{safe_value(action, 'action_plan')}"
                )

                st.write(
                    f"**Department:** "
                    f"{safe_value(action, 'responsible_department')}"
                )

                st.write(
                    f"**Assigned To:** "
                    f"{safe_value(action, 'assigned_to')}"
                )

                st.write(
                    f"**Priority:** "
                    f"{safe_value(action, 'priority')}"
                )

                st.write(
                    f"**Target Date:** "
                    f"{safe_value(action, 'target_date')}"
                )

                st.write(
                    f"**Status:** "
                    f"{safe_value(action, 'status')}"
                )


    with st.expander(
        "➕ Assign New Corrective Action",
        expanded=not bool(existing_actions),
    ):

        action_plan = st.text_area(
            "Action Plan",
            placeholder=(
                "Describe the corrective action..."
            ),
        )

        action_col1, action_col2 = st.columns(2)

        with action_col1:

            department = st.text_input(
                "Responsible Department"
            )

            assigned_to = st.text_input(
                "Assigned To"
            )


        with action_col2:

            action_priority = st.selectbox(
                "Priority",
                [
                    "High",
                    "Medium",
                    "Low",
                ],
            )

            target_date = st.date_input(
                "Target Date",
                value=date.today(),
            )


        if st.button(
            "📌 Assign Corrective Action",
            width='stretch',
        ):

            if not action_plan.strip():

                st.warning(
                    "Please enter an action plan."
                )

            elif not department.strip():

                st.warning(
                    "Please enter the responsible department."
                )

            else:

                try:

                    conn.execute(
                        """
                        INSERT INTO corrective_actions (
                            report_id,
                            action_plan,
                            responsible_department,
                            assigned_to,
                            priority,
                            target_date,
                            status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            selected_id,
                            action_plan.strip(),
                            department.strip(),
                            assigned_to.strip(),
                            action_priority,
                            target_date.isoformat(),
                            "Assigned",
                        ),
                    )


                    conn.execute(
                        """
                        UPDATE reports
                        SET report_status = ?
                        WHERE id = ?
                        """,
                        (
                            "Action Assigned",
                            selected_id,
                        ),
                    )


                    if table_exists(
                        conn,
                        "audit_log",
                    ):

                        conn.execute(
                            """
                            INSERT INTO audit_log (
                                report_id,
                                user_name,
                                role,
                                action,
                                field_name,
                                old_value,
                                new_value
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                selected_id,
                                active_role,
                                active_role,
                                "Assign Corrective Action",
                                "report_status",
                                current_status,
                                "Action Assigned",
                            ),
                        )


                    conn.commit()


                    st.success(
                        "✅ Corrective action assigned."
                    )

                    st.rerun()


                except Exception as e:

                    conn.rollback()

                    st.error(
                        "❌ Could not assign corrective action."
                    )

                    st.exception(e)


else:

    if current_status in [
        "Pending HSE Review",
    ]:

        st.info(
            "Review and accept/correct the report before "
            "assigning a corrective action."
        )

    else:

        st.info(
            "No corrective action is currently available "
            "for this workflow state."
        )


# ============================================================
# 5. AUDIT HISTORY
# ============================================================

st.divider()

st.markdown(
    "### 5. Audit History"
)


if table_exists(
    conn,
    "audit_log",
):

    audit_rows = conn.execute(
        """
        SELECT *
        FROM audit_log
        WHERE report_id = ?
        ORDER BY datetime(timestamp) DESC
        """,
        (selected_id,),
    ).fetchall()


    if audit_rows:

        audit_data = []

        for row in audit_rows:

            audit_data.append(
                {
                    "Time": safe_value(
                        row,
                        "timestamp",
                    ),
                    "User": safe_value(
                        row,
                        "user_name",
                    ),
                    "Role": safe_value(
                        row,
                        "role",
                    ),
                    "Action": safe_value(
                        row,
                        "action",
                    ),
                    "Field": safe_value(
                        row,
                        "field_name",
                    ),
                    "Old Value": safe_value(
                        row,
                        "old_value",
                    ),
                    "New Value": safe_value(
                        row,
                        "new_value",
                    ),
                }
            )


        st.dataframe(
            audit_data,
            width='stretch',
            hide_index=True,
        )

    else:

        st.info(
            "No audit history is available for this report."
        )

else:

    st.info(
        "Audit log table is not available."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "SafeSignalAI • HSE Review Workflow • "
    "Original AI predictions are preserved for auditability."
)


conn.close()