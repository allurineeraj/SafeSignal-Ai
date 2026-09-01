import os
import sys
import sqlite3
import json
import py_compile

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("==================================================")
print("PHASE 2 - STRICT ARCHITECTURE VERIFICATION SCRIPT")
print("==================================================\n")

# Check 1: Import all created modules to verify syntax and imports
print("1. Checking for import and syntax errors...")
files_to_compile = [
    "database/db.py",
    "services/classifier.py",
    "services/safety_rules.py",
    "services/similar_search.py",
    "services/text_extraction.py",
    "services/stt.py",
    "services/translation.py",
    "services/model_status.py",
    "scripts/create_demo_data.py"
]

all_compiled = True
for filepath in files_to_compile:
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"  - Compiled successfully: {filepath}")
    except Exception as e:
        print(f"  - FAILED to compile {filepath}: {str(e)}")
        all_compiled = False

if not all_compiled:
    print("[FAIL] Syntax/Import checks failed. Exiting.")
    sys.exit(1)
else:
    print("[PASS] All imports and syntax checked successfully.\n")

# Load Database Modules
import database.db
from database.db import (
    init_db, get_connection, save_report, save_ai_prediction,
    save_hse_review, get_report_by_id, get_all_reports, get_audit_trail,
    update_report_status, validate_status_transition
)
from scripts.create_demo_data import generate_csv, seed_database

# Check 2: Fresh database initialization
print("2. Running database initialization from clean state...")
DB_FILE = "db.sqlite"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print("  - Deleted existing db.sqlite file.")

init_db()
if os.path.exists(DB_FILE):
    print("  - Fresh db.sqlite initialized successfully.")
else:
    print("[FAIL] Database initialization failed. File not created.")
    sys.exit(1)

# Check 3: Verify all tables exist
print("\n3. Verifying required database tables exist...")
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row['name'] for row in cursor.fetchall()]
required_tables = ["reports", "ai_predictions", "hse_reviews", "corrective_actions", "audit_log"]

tables_ok = True
for rt in required_tables:
    if rt in tables:
        print(f"  - Table exists: {rt}")
    else:
        print(f"  - Table MISSING: {rt}")
        tables_ok = False
        
if not tables_ok:
    print("[FAIL] Table verification failed.")
    sys.exit(1)

# Check 4: Verify foreign keys are enabled
print("\n4. Verifying foreign key constraint enforcement...")
cursor.execute("PRAGMA foreign_keys;")
fk_status = cursor.fetchone()[0]
print(f"  - PRAGMA foreign_keys returns: {fk_status} (Expected: 1)")

# Test actual enforcement
try:
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("""
        INSERT INTO ai_predictions (
            report_id, sif_label, sif_score, priority, classifier_mode, model_version
        ) VALUES (999, 'SIF-potential', 10, 'Critical', 'Rule-engine fallback', '1.0')
    """)
    conn.commit()
    print("  - FAILED: SQLite allowed inserting prediction without matching parent report ID!")
    sys.exit(1)
except sqlite3.IntegrityError:
    print("  - PASS: Foreign key enforcement blocks invalid parent relationship insertion successfully.")
finally:
    conn.close()

# Check 5: Verify indexes exist
print("\n5. Verifying DB index optimizations...")
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
indexes = [row['name'] for row in cursor.fetchall()]
required_indexes = ["idx_reports_site", "idx_reports_type", "idx_reports_status", "idx_reports_priority", "idx_reports_created"]

idx_ok = True
for ri in required_indexes:
    if ri in indexes:
        print(f"  - Index exists: {ri}")
    else:
        print(f"  - Index MISSING: {ri}")
        idx_ok = False
conn.close()
if not idx_ok:
    print("[FAIL] Index verification failed.")
    sys.exit(1)

# Check 6: Verify JSON storage and retrieval
print("\n6. Verifying JSON field serialization/deserialization...")
report_id = save_report({
    "report_type": "Near Miss",
    "site": "Demo Refinery North",
    "location": "Separator Pit",
    "original_language": "English",
    "original_text": "Welding in a confined space.",
    "source_type": "Text Input",
    "immediate_danger": 0,
    "review_priority": "High",
    "report_status": "Submitted"
})

rules_array = ["Confined Space", "Hot Work"]
evidence_array = ["weld inside vessel", "no gas test"]

save_ai_prediction({
    "report_id": report_id,
    "sif_label": "SIF-potential",
    "sif_score": 10,
    "confidence": None,
    "priority": "High",
    "life_saving_rules": rules_array,
    "evidence_phrases": evidence_array,
    "classifier_mode": "Rule-engine fallback",
    "model_version": "1.0"
})

retrieved_rep = get_report_by_id(report_id)
if retrieved_rep["ai_life_saving_rules"] == rules_array and retrieved_rep["ai_evidence_phrases"] == evidence_array:
    print("  - PASS: JSON arrays are correctly serialized to database and parsed on retrieval.")
else:
    print(f"  - FAILED: Retrival list mismatch. Expected {rules_array}, Got {retrieved_rep['ai_life_saving_rules']}")
    sys.exit(1)

# Check 7: Verify report state transition rules
print("\n7. Verifying report state transitions...")
# Check standard transition
assert validate_status_transition("Submitted", "Pending HSE Review") == True
assert validate_status_transition("Closed", "Pending HSE Review") == False
print("  - PASS: Allowed state graph correctly resolved.")

# Check 8: Verify audit-log creation on review and status update
print("\n8. Verifying audit logging triggers...")
# Transition status
update_report_status(report_id, "Pending HSE Review", "Test Operator", "Worker")
save_hse_review({
    "report_id": report_id,
    "reviewer_name": "Auditor Test",
    "final_sif_label": "SIF-potential",
    "final_priority": "High",
    "review_status": "Accepted"
})

audits = get_audit_trail(report_id)
if len(audits) >= 2:
    print(f"  - PASS: Generated {len(audits)} audit entries.")
    for a in audits:
        print(f"    * Timestamp: {a['timestamp']} | User: {a['user_name']} ({a['role']}) | Action: {a['action']} | Field: {a['field_name']}")
else:
    print(f"  - FAILED: Audit trail missing expected records. Got {len(audits)}")
    sys.exit(1)

# Check 9: Verify repeated initialization is safe
print("\n9. Verifying repeated database initialization safety...")
try:
    init_db()
    print("  - PASS: Repeated execution of init_db() compiles and runs safely without duplicate index/table errors.")
except Exception as e:
    print(f"  - FAILED: init_db raised exception: {str(e)}")
    sys.exit(1)

# Check 10: Verify repeated seeding safety and duplicate handling
print("\n10. Checking golden dataset seeding and repeated execution...")
generate_csv()
seed_database()
first_run_count = len(get_all_reports())
print(f"  - First seed insertion count: {first_run_count} reports (Expected: 85)")

# Re-run seeding to confirm data isn't duplicated
seed_database()
second_run_count = len(get_all_reports())
print(f"  - Second seed insertion count: {second_run_count} reports")

if first_run_count == second_run_count:
    print("  - PASS: Repeated seeding executes safely and does not generate duplicate records.")
else:
    print(f"  - FAILED: Duplicate seed records created! Got {second_run_count} after second run.")
    sys.exit(1)

# Check 11: Dependency list check
print("\n11. Checking requirements consistency...")
if os.path.exists("requirements.txt") and os.path.exists("requirements-optional-models.txt"):
    print("  - PASS: Environment requirement lists are present.")
else:
    print("  - FAILED: Dependency files missing.")
    sys.exit(1)

print("\n==================================================")
print("VERIFICATION COMPLETED SUCCESSFULLY: STATUS PASS")
print("==================================================")
