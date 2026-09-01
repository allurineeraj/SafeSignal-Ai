import os
import sqlite3
import json
import hashlib
import binascii
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db.sqlite")

# Valid report statuses
VALID_STATUSES = {
    'Submitted', 'Processing', 'Pending HSE Review', 'Accepted',
    'Corrected', 'Action Assigned', 'Action In Progress', 'Closed',
    'Rejected', 'Duplicate'
}

# State machine allowed transitions
# Key: current status, Value: set of target statuses it is allowed to transition to
STATE_TRANSITIONS = {
    "Submitted": {"Processing", "Pending HSE Review", "Rejected"},
    "Processing": {"Pending HSE Review"},
    "Pending HSE Review": {"Accepted", "Corrected", "Rejected", "Duplicate", "Closed"},
    "Accepted": {"Action Assigned", "Action In Progress", "Closed", "Rejected"},
    "Corrected": {"Action Assigned", "Action In Progress", "Closed", "Rejected"},
    "Action Assigned": {"Action In Progress", "Closed"},
    "Action In Progress": {"Closed"},
    "Closed": set(),      # Terminal state
    "Rejected": set(),    # Terminal state
    "Duplicate": set()    # Terminal state
}

def get_connection():
    """Establishes a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def validate_status_transition(old_status: str, new_status: str) -> bool:
    """Verifies if the report status transition is valid according to the state machine.
    Allowing any new status if the report is new (old_status is None).
    """
    if old_status is None:
        return new_status in VALID_STATUSES
        
    if old_status == new_status:
        return True
        
    if old_status not in STATE_TRANSITIONS:
        return False
        
    return new_status in STATE_TRANSITIONS[old_status]

def init_db():
    """Initializes the database schema, creating tables and indexes if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Reports Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_type TEXT NOT NULL,
        site TEXT NOT NULL,
        location TEXT NOT NULL,
        original_text TEXT NOT NULL,
        original_language TEXT DEFAULT 'English',
        translated_text TEXT,
        immediate_action TEXT,
        anonymous INTEGER DEFAULT 0,
        submitted_on_behalf INTEGER DEFAULT 0,
        submitted_by TEXT,
        source_type TEXT DEFAULT 'web_form',
        audio_path TEXT,
        image_path TEXT,
        document_path TEXT,
        immediate_danger INTEGER DEFAULT 0,
        review_priority TEXT,
        report_status TEXT DEFAULT 'Submitted',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. AI Predictions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER UNIQUE NOT NULL,
        sif_label TEXT NOT NULL,
        sif_score INTEGER NOT NULL,
        confidence REAL, -- NULL/Unavailable if model offline
        priority TEXT NOT NULL,
        activity TEXT,
        hazard TEXT,
        energy_source TEXT,
        exposure TEXT,
        failed_barrier TEXT,
        potential_consequence TEXT,
        life_saving_rules TEXT, -- JSON string array
        evidence_phrases TEXT,  -- JSON string array
        actual_injury TEXT,
        explanation TEXT,
        llm_provider TEXT,
        llm_model TEXT,
        llm_analysis_status TEXT,
        llm_confidence REAL,
        classifier_mode TEXT NOT NULL,
        model_version TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
    );
    """)

    # 3. HSE Reviews Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hse_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER UNIQUE NOT NULL,
        reviewer_name TEXT NOT NULL,
        final_sif_label TEXT NOT NULL,
        final_priority TEXT NOT NULL,
        final_activity TEXT,
        final_hazard TEXT,
        final_energy_source TEXT,
        final_exposure TEXT,
        final_failed_barrier TEXT,
        final_potential_consequence TEXT,
        final_life_saving_rules TEXT, -- JSON string array
        final_actual_injury TEXT,
        hse_comments TEXT,
        review_status TEXT NOT NULL,
        reviewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
    );
    """)

    # 4. Corrective Actions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS corrective_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        action_plan TEXT NOT NULL,
        responsible_department TEXT NOT NULL,
        assigned_to TEXT,
        priority TEXT NOT NULL,
        target_date TEXT NOT NULL,
        status TEXT NOT NULL,
        completion_notes TEXT,
        completed_at DATETIME,
        assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
    );
    """)

    # 5. Audit Log Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        user_name TEXT NOT NULL,
        role TEXT NOT NULL,
        action TEXT NOT NULL,
        field_name TEXT,
        old_value TEXT,
        new_value TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
    );
    """)

    # Index Optimizations for Queue & Dashboard Queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_site ON reports (site);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_type ON reports (report_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (report_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_priority ON reports (review_priority);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports (created_at);")
    
    # 6. Users Table (Authentication)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL
    );
    """)
    
    conn.commit()
    conn.close()
    
    # Initialize demo users if none exist
    init_demo_users()
# ============================================================
# AUTHENTICATION
# ============================================================

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC with a random salt."""
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return binascii.hexlify(salt).decode('ascii') + ':' + binascii.hexlify(pw_hash).decode('ascii')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a password against a PBKDF2-HMAC hash."""
    try:
        salt_hex, pw_hash_hex = hashed_password.split(':')
        salt = binascii.unhexlify(salt_hex)
        pw_hash = binascii.unhexlify(pw_hash_hex)
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000) == pw_hash
    except Exception:
        return False

def init_demo_users():
    """Initializes demo users if the users table is empty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        demo_users = [
            ("HSE001", "HSE@1234", "HSE Officer"),
            ("MGR001", "MGR@1234", "HSE Manager")
        ]
        for uid, pwd, role in demo_users:
            cursor.execute("INSERT INTO users (user_id, password_hash, role) VALUES (?, ?, ?)", 
                           (uid, hash_password(pwd), role))
        conn.commit()
    conn.close()

def verify_credentials(user_id: str, password: str) -> dict:
    """Verifies credentials and returns user details if valid."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, password_hash, role FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and verify_password(password, row['password_hash']):
        return {"user_id": row["user_id"], "role": row["role"]}
    return None

# ============================================================
# AUDIT AND REPORTS
# ============================================================
def log_audit(report_id: int, user_name: str, role: str, action: str, field_name: str = None, old_value: str = None, new_value: str = None):
    """Reusable audit-logging entry function."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (report_id, user_name, role, action, field_name, old_value, new_value, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_id, user_name, role, action, field_name, 
        str(old_value) if old_value is not None else None, 
        str(new_value) if new_value is not None else None,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def save_report(report_data: dict) -> int:
    """Inserts a new safety report. Enforces enum-status and computes initial values."""
    status = report_data.get("report_status", "Submitted")
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid initial report status: {status}")
        
    conn = get_connection()
    cursor = conn.cursor()
    
    keys = list(report_data.keys())
    placeholders = ",".join(["?"] * len(keys))
    query = f"INSERT INTO reports ({','.join(keys)}) VALUES ({placeholders})"
    
    cursor.execute(query, [report_data[k] for k in keys])
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Log creation audit record
    log_audit(
        report_id=report_id, 
        user_name=report_data.get("submitted_by") or "System / Worker", 
        role="Worker / Observer" if not report_data.get("submitted_on_behalf") else "Supervisor", 
        action="Submit Report", 
        new_value=status
    )
    
    return report_id

def update_report_status(report_id: int, new_status: str, user_name: str, role: str) -> None:
    """Updates report status after validating the state transition. Logs change to audit trail."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status value: {new_status}")
        
    conn = get_connection()
    cursor = conn.cursor()
    
    # Fetch current status
    cursor.execute("SELECT report_status FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Report ID #{report_id} not found.")
        
    old_status = row['report_status']
    
    # State transition validation
    if not validate_status_transition(old_status, new_status):
        conn.close()
        raise ValueError(f"Invalid state transition from '{old_status}' to '{new_status}'.")
        
    if old_status != new_status:
        cursor.execute("UPDATE reports SET report_status = ? WHERE id = ?", (new_status, report_id))
        conn.commit()
        conn.close()
        log_audit(
            report_id=report_id,
            user_name=user_name,
            role=role,
            action="Update Status",
            field_name="report_status",
            old_value=old_status,
            new_value=new_status
        )
    else:
        conn.close()

def save_ai_prediction(prediction_data: dict) -> None:
    """Saves safety engine predictions. Checks that JSON structures are serialized to strings."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for key in ['life_saving_rules', 'evidence_phrases']:
        if key in prediction_data and isinstance(prediction_data[key], list):
            prediction_data[key] = json.dumps(prediction_data[key])
            
    keys = list(prediction_data.keys())
    placeholders = ",".join(["?"] * len(keys))
    
    # Construct DO UPDATE SET clause for all fields except report_id
    update_fields = [k for k in keys if k != "report_id"]
    update_clause = ", ".join([f"{k}=excluded.{k}" for k in update_fields])
    
    query = f"""
        INSERT INTO ai_predictions ({','.join(keys)}) 
        VALUES ({placeholders}) 
        ON CONFLICT(report_id) DO UPDATE SET {update_clause}
    """
    
    cursor.execute(query, [prediction_data[k] for k in keys])
    conn.commit()
    conn.close()

def save_hse_review(review_data: dict) -> None:
    """Saves or updates the HSE review record. Triggers transition check and writes to audit logs."""
    conn = get_connection()
    cursor = conn.cursor()
    
    report_id = review_data['report_id']
    reviewer = review_data['reviewer_name']
    new_status = review_data['review_status']
    
    # Parse list
    if 'final_life_saving_rules' in review_data and isinstance(review_data['final_life_saving_rules'], list):
        review_data['final_life_saving_rules'] = json.dumps(review_data['final_life_saving_rules'])
        
    # Check status transitions
    cursor.execute("SELECT report_status FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    old_status = row['report_status'] if row else None
    
    if old_status and not validate_status_transition(old_status, new_status):
        conn.close()
        raise ValueError(f"Invalid state transition from '{old_status}' to '{new_status}' during HSE Review.")

    # Check if review already exists
    cursor.execute("SELECT * FROM hse_reviews WHERE report_id = ?", (report_id,))
    old_review = cursor.fetchone()
    
    if old_review:
        # Audit modifications
        old_review_dict = dict(old_review)
        for field, new_val in review_data.items():
            if field in ['report_id', 'reviewer_name']:
                continue
            old_val = old_review_dict.get(field)
            
            # Text normalization
            str_old = str(old_val) if old_val is not None else ""
            str_new = str(new_val) if new_val is not None else ""
            
            if str_old != str_new:
                cursor.execute("""
                    INSERT INTO audit_log (report_id, user_name, role, action, field_name, old_value, new_value, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id, reviewer, 'HSE Officer', 'Update Review Field', field, str_old, str_new,
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                ))
                
        # Perform updates
        update_pairs = [f"{k} = ?" for k in review_data.keys() if k != 'report_id']
        params = [review_data[k] for k in review_data.keys() if k != 'report_id'] + [report_id]
        cursor.execute(f"UPDATE hse_reviews SET {','.join(update_pairs)} WHERE report_id = ?", params)
    else:
        # Create audit for review creation
        cursor.execute("""
            INSERT INTO audit_log (report_id, user_name, role, action, field_name, old_value, new_value, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id, reviewer, 'HSE Officer', 'Create Review', None, None, None,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        keys = list(review_data.keys())
        placeholders = ",".join(["?"] * len(keys))
        cursor.execute(f"INSERT INTO hse_reviews ({','.join(keys)}) VALUES ({placeholders})", [review_data[k] for k in keys])
        
    # Commit changes
    conn.commit()
    conn.close()
    
    # Synchronize report status
    update_report_status(report_id, new_status, reviewer, "HSE Officer")

def add_corrective_action(action_data: dict) -> int:
    """Inserts a new corrective action for a report."""
    conn = get_connection()
    cursor = conn.cursor()
    
    keys = list(action_data.keys())
    placeholders = ",".join(["?"] * len(keys))
    query = f"INSERT INTO corrective_actions ({','.join(keys)}) VALUES ({placeholders})"
    
    cursor.execute(query, [action_data[k] for k in keys])
    action_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Audit log entry
    log_audit(
        report_id=action_data['report_id'],
        user_name="HSE Officer",
        role="HSE Officer",
        action="Assign Corrective Action",
        field_name="corrective_action_id",
        new_value=str(action_id)
    )
    
    # Synchronize report status to Action Assigned
    update_report_status(action_data['report_id'], "Action Assigned", "HSE Officer", "HSE Officer")
    
    return action_id

def update_corrective_action_status(action_id: int, new_status: str, completion_notes: str = None, user_name: str = "HSE Officer") -> None:
    """Updates status of a corrective action (Assigned, In Progress, Completed). Logs to audit."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT report_id, status FROM corrective_actions WHERE id = ?", (action_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Corrective action ID #{action_id} not found.")
        
    report_id = row['report_id']
    old_status = row['status']
    
    if old_status != new_status:
        if new_status == "Completed":
            cursor.execute("""
                UPDATE corrective_actions 
                SET status = ?, completion_notes = ?, completed_at = ? 
                WHERE id = ?
            """, (new_status, completion_notes, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), action_id))
        else:
            cursor.execute("UPDATE corrective_actions SET status = ? WHERE id = ?", (new_status, action_id))
            
        conn.commit()
        conn.close()
        
        log_audit(
            report_id=report_id,
            user_name=user_name,
            role="HSE Officer",
            action="Update Corrective Action Status",
            field_name="action_status",
            old_value=old_status,
            new_value=new_status
        )
        
        # Sync report status to closed if all actions are completed, or in progress if one is started
        sync_report_status_from_actions(report_id, user_name)
    else:
        conn.close()

def sync_report_status_from_actions(report_id: int, user_name: str) -> None:
    """Inspects corrective actions and moves reports to Closed or Action In Progress if appropriate."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status FROM corrective_actions WHERE report_id = ?", (report_id,))
    actions = cursor.fetchall()
    conn.close()
    
    if not actions:
        return
        
    statuses = [a['status'] for a in actions]
    
    # If all actions are completed -> Closed
    if all(s == 'Completed' for s in statuses):
        update_report_status(report_id, "Closed", user_name, "HSE Officer")
    # If any action is in progress -> Action In Progress
    elif any(s == 'In Progress' for s in statuses):
        update_report_status(report_id, "Action In Progress", user_name, "HSE Officer")

def get_report_by_id(report_id: int) -> dict:
    """Returns detailed observation dictionary matching predictions and reviews."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*,
               p.sif_label as ai_sif_label, p.sif_score as ai_sif_score, p.confidence as ai_confidence,
               p.priority as ai_priority, p.activity as ai_activity, p.hazard as ai_hazard,
               p.energy_source as ai_energy_source, p.exposure as ai_exposure, p.failed_barrier as ai_failed_barrier,
               p.potential_consequence as ai_potential_consequence, p.life_saving_rules as ai_life_saving_rules,
               p.evidence_phrases as ai_evidence_phrases, p.classifier_mode as ai_classifier_mode,
               p.model_version as ai_model_version, p.llm_provider as ai_llm_provider,
               p.llm_model as ai_llm_model, p.llm_analysis_status as ai_llm_analysis_status,
               p.llm_confidence as ai_llm_confidence, p.actual_injury as ai_actual_injury,
               p.explanation as ai_explanation,
               rev.reviewer_name, rev.final_sif_label, rev.final_priority, rev.final_activity,
               rev.final_hazard, rev.final_energy_source, rev.final_exposure, rev.final_failed_barrier,
               rev.final_potential_consequence, rev.final_life_saving_rules, rev.hse_comments, rev.review_status
        FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
        WHERE r.id = ?
    """, (report_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        res = dict(row)
        for k in ['ai_life_saving_rules', 'ai_evidence_phrases', 'final_life_saving_rules']:
            if res.get(k):
                try:
                    res[k] = json.loads(res[k])
                except:
                    res[k] = []
            else:
                res[k] = []
        return res
    return None

def get_all_reports(filters: dict = None) -> list[dict]:
    """Retrieves reports matching filters."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT r.id, r.created_at, r.report_type, r.site, r.location, r.original_text, r.translated_text,
               r.report_status, r.immediate_danger, r.review_priority,
               p.sif_label as ai_sif_label, p.confidence as ai_confidence, p.priority as ai_priority,
               p.life_saving_rules as ai_life_saving_rules,
               p.llm_provider as ai_llm_provider, p.llm_model as ai_llm_model,
               p.llm_analysis_status as ai_llm_analysis_status, p.llm_confidence as ai_llm_confidence,
               p.classifier_mode as ai_classifier_mode, p.model_version as ai_model_version,
               p.actual_injury as ai_actual_injury, p.explanation as ai_explanation,
               rev.final_sif_label, rev.final_priority, rev.final_life_saving_rules
        FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
    """
    conditions = []
    params = []
    
    if filters:
        if filters.get('site'):
            conditions.append("r.site = ?")
            params.append(filters['site'])
        if filters.get('report_type'):
            conditions.append("r.report_type = ?")
            params.append(filters['report_type'])
        if filters.get('review_status'):
            conditions.append("r.report_status = ?")
            params.append(filters['review_status'])
        if filters.get('sif_label'):
            conditions.append("COALESCE(rev.final_sif_label, p.sif_label) = ?")
            params.append(filters['sif_label'])
        if filters.get('priority'):
            conditions.append("COALESCE(rev.final_priority, p.priority) = ?")
            params.append(filters['priority'])
        if filters.get('immediate_danger') is not None:
            conditions.append("r.immediate_danger = ?")
            params.append(filters['immediate_danger'])
            
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY r.immediate_danger DESC, r.created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        for k in ['ai_life_saving_rules', 'final_life_saving_rules']:
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except:
                    d[k] = []
            else:
                d[k] = []
        results.append(d)
    return results

def get_audit_trail(report_id: int) -> list[dict]:
    """Retrieves changes history for a report."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE report_id = ? ORDER BY timestamp DESC", (report_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats() -> dict:
    """Aggregates and returns core KPIs for the Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM reports")
    total = cursor.fetchone()[0]
    
    if total == 0:
        conn.close()
        return {
            'total_reports': 0, 'sif_count': 0, 'non_sif_count': 0,
            'review_req_count': 0, 'critical_count': 0, 'closed_count': 0,
            'open_actions_count': 0, 'sif_percentage': 0.0,
            'highest_risk_site': 'None', 'most_freq_rule': 'None', 'most_freq_barrier': 'None'
        }
        
    cursor.execute("""
        SELECT COUNT(*) FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
        WHERE COALESCE(rev.final_sif_label, p.sif_label) = 'SIF-potential'
    """)
    sif_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
        WHERE COALESCE(rev.final_sif_label, p.sif_label) = 'Review Required'
    """)
    review_req_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
        WHERE COALESCE(rev.final_sif_label, p.sif_label) = 'Non-SIF-potential'
    """)
    non_sif_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE review_priority = 'Critical'")
    critical_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE report_status = 'Closed'")
    closed_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM corrective_actions WHERE status != 'Completed'")
    open_actions = cursor.fetchone()[0]
    
    sif_density = (sif_count / total) * 100
    
    # Highest risk site
    cursor.execute("""
        SELECT r.site, COUNT(*) as c FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
        WHERE COALESCE(rev.final_sif_label, p.sif_label) = 'SIF-potential'
        GROUP BY r.site ORDER BY c DESC LIMIT 1
    """)
    row = cursor.fetchone()
    highest_risk_site = row['site'] if row else "None"
    
    # Most frequent failed barrier
    cursor.execute("""
        SELECT COALESCE(rev.final_failed_barrier, p.failed_barrier) as barrier, COUNT(*) as c
        FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
        WHERE barrier IS NOT NULL AND barrier != '' AND barrier != 'Unknown — requires HSE review'
        GROUP BY barrier ORDER BY c DESC LIMIT 1
    """)
    row = cursor.fetchone()
    most_freq_barrier = row['barrier'] if row else "None"
    
    # Most frequent rule
    cursor.execute("""
        SELECT COALESCE(rev.final_life_saving_rules, p.life_saving_rules) as rules
        FROM reports r
        LEFT JOIN ai_predictions p ON r.id = p.report_id
        LEFT JOIN hse_reviews rev ON r.id = rev.report_id
    """)
    rule_rows = cursor.fetchall()
    rule_counts = {}
    for row in rule_rows:
        rules_str = row['rules']
        if rules_str:
            try:
                rules_list = json.loads(rules_str)
                for r in rules_list:
                    rule_counts[r] = rule_counts.get(r, 0) + 1
            except:
                pass
    most_freq_rule = max(rule_counts, key=rule_counts.get) if rule_counts else "None"
    
    conn.close()
    return {
        'total_reports': total,
        'sif_count': sif_count,
        'non_sif_count': non_sif_count,
        'review_req_count': review_req_count,
        'critical_count': critical_count,
        'closed_count': closed_count,
        'open_actions_count': open_actions,
        'sif_percentage': round(sif_density, 1),
        'highest_risk_site': highest_risk_site,
        'most_freq_rule': most_freq_rule,
        'most_freq_barrier': most_freq_barrier
    }
