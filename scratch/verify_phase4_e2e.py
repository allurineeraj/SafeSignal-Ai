import os
import sys
import json
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.db import (
    init_db, get_connection, save_report, save_ai_prediction,
    save_hse_review, update_report_status, get_report_by_id,
    get_all_reports, get_audit_trail, add_corrective_action,
    validate_status_transition, log_audit
)
from services.classifier import classify_report

print("==================================================")
print("PHASE 4 - E2E PROGRAMMATIC INTEGRATION TESTS")
print("==================================================\n")

# Clear tables for fresh validation run
init_db()
conn = get_connection()
cursor = conn.cursor()
cursor.execute("DELETE FROM reports;")
cursor.execute("DELETE FROM ai_predictions;")
cursor.execute("DELETE FROM hse_reviews;")
cursor.execute("DELETE FROM audit_log;")
cursor.execute("DELETE FROM corrective_actions;")
conn.commit()
conn.close()

# Helpers
def helper_save_prediction(report_id, res):
    ai_data = {
        "report_id": report_id,
        "sif_label": res["sif_label"],
        "sif_score": res["sif_score"],
        "confidence": res.get("ml_confidence"),
        "priority": res["priority"],
        "activity": res["activity"],
        "hazard": res["hazards"],
        "energy_source": res["energy_sources"],
        "exposure": res["exposure"],
        "failed_barrier": ", ".join(res["failed_barriers"]) if isinstance(res["failed_barriers"], list) else res["failed_barriers"],
        "potential_consequence": res["potential_consequences"],
        "life_saving_rules": res["life_saving_rules"],
        "evidence_phrases": res["evidence_phrases"],
        "classifier_mode": res["classifier_mode"],
        "model_version": res["model_version"]
    }
    save_ai_prediction(ai_data)

# 1. E2E Worker Submission Flow
print("1. E2E WORKER SUBMISSION FLOW:")
res_class = classify_report(
    "During pump maintenance, electrical isolation was not verified. The technician began removing the coupling guard while the pump was still connected to power.",
    immediate_danger=False
)

report_data = {
    "report_type": "Near Miss",
    "site": "Demo Site",
    "location": "Pump Maintenance Area",
    "original_text": "During pump maintenance, electrical isolation was not verified. The technician began removing the coupling guard while the pump was still connected to power.",
    "original_language": "English",
    "immediate_action": "Work stopped and supervisor notified.",
    "submitted_by": "Worker 123",
    "submitted_on_behalf": 0,
    "immediate_danger": 0,
    "source_type": "web_form",
    "review_priority": res_class["priority"],
    "report_status": "Submitted"
}

report_id = save_report(report_data)
helper_save_prediction(report_id, res_class)
update_report_status(report_id, "Pending HSE Review", "System", "System")

# Verify database integrity
report = get_report_by_id(report_id)
print(f"  * Created Report ID: #{report['id']}")
print(f"  * original_text: \"{report['original_text'][:50]}...\"")
print(f"  * report_type: {report['report_type']}")
print(f"  * site: {report['site']}")
print(f"  * location: {report['location']}")
print(f"  * immediate_action: {report['immediate_action']}")
print(f"  * immediate_danger: {report['immediate_danger']} (Expected: 0)")
print(f"  * report_status: {report['report_status']} (Expected: Pending HSE Review)")
print(f"  * SIF Label (AI): {report['ai_sif_label']}")
print(f"  * SIF Score (AI): {report['ai_sif_score']}")
print(f"  * Priority (AI): {report['ai_priority']}")
print(f"  * Life-Saving Rules matched: {report['ai_life_saving_rules']}")
print("\n" + "="*50 + "\n")

# 2. Immediate Danger Submission
print("2. IMMEDIATE DANGER HANDLING:")
res_danger = classify_report("Worker is currently exposed to an unguarded rotating machine.", immediate_danger=True)

danger_report_data = {
    "report_type": "Unsafe Act",
    "site": "Demo Site B",
    "location": "Machine Shop",
    "original_text": "Worker is currently exposed to an unguarded rotating machine.",
    "original_language": "English",
    "immediate_action": "None",
    "submitted_by": "Worker 123",
    "submitted_on_behalf": 0,
    "immediate_danger": 1,
    "source_type": "web_form",
    "review_priority": res_danger["priority"],
    "report_status": "Submitted"
}

danger_report_id = save_report(danger_report_data)
helper_save_prediction(danger_report_id, res_danger)
update_report_status(danger_report_id, "Pending HSE Review", "System", "System")

danger_report = get_report_by_id(danger_report_id)
print(f"  * Created Danger Report ID: #{danger_report['id']}")
print(f"  * immediate_danger: {danger_report['immediate_danger']} (Expected: 1)")
print(f"  * review_priority: {danger_report['review_priority']} (Expected: Critical)")
print("\n" + "="*50 + "\n")

# 3. HSE Queue Retrieval and Sorting
print("3. HSE QUEUE RETRIEVAL AND SORTING:")
all_reports = get_all_reports()
print(f"  * Total reports returned by queue: {len(all_reports)} (Expected: 2)")
# Since danger_report has immediate_danger=1 and priority=Critical, it must sort first
print(f"  * First report ID in queue: #{all_reports[0]['id']} (Expected: #{danger_report_id})")
print(f"  * Second report ID in queue: #{all_reports[1]['id']} (Expected: #{report_id})")
print("\n" + "="*50 + "\n")

# 4. Accept AI Result
print("4. ACCEPT AI RESULT ACTION:")
# Select report #1 (Pump isolation) and accept AI prediction values
review_data = {
    "report_id": report_id,
    "reviewer_name": "HSE Officer Bob",
    "final_sif_label": report["ai_sif_label"],
    "final_priority": report["ai_priority"],
    "final_activity": report["ai_activity"],
    "final_hazard": report["ai_hazard"],
    "final_energy_source": report["ai_energy_source"],
    "final_exposure": report["ai_exposure"],
    "final_failed_barrier": report["ai_failed_barrier"],
    "final_potential_consequence": report["ai_potential_consequence"],
    "final_life_saving_rules": report["ai_life_saving_rules"],
    "hse_comments": "AI results accepted.",
    "review_status": "Accepted"
}
save_hse_review(review_data)

# Verify records
accepted_report = get_report_by_id(report_id)
print(f"  * report_status: {accepted_report['report_status']} (Expected: Accepted)")
print(f"  * review_status: {accepted_report['review_status']} (Expected: Accepted)")
print(f"  * original ai_sif_label: {accepted_report['ai_sif_label']} (Expected: SIF-potential)")
print(f"  * final_sif_label: {accepted_report['final_sif_label']} (Expected: SIF-potential)")

# Check audit logging for Accept
audit_accept = get_audit_trail(report_id)
print(f"  * Audit log actions for #{report_id}: {[a['action'] for a in audit_accept]}")
print("\n" + "="*50 + "\n")

# 5. HSE Manual Correction Override
print("5. HSE MANUAL CORRECTION OVERRIDE:")
# Select report #2 (Danger rotating machine) and change SIF-potential to Review Required
corr_data = {
    "report_id": danger_report_id,
    "reviewer_name": "HSE Officer Bob",
    "final_sif_label": "Review Required", # Override SIF label
    "final_priority": "High",            # Override priority
    "final_activity": "Operating machine",
    "final_hazard": "Mechanical hazard",
    "final_energy_source": "Mechanical",
    "final_exposure": "Worker exposed",
    "final_failed_barrier": "Guards missing",
    "final_potential_consequence": "Entanglement",
    "final_life_saving_rules": ["Line of Fire"],
    "hse_comments": "Corrected SIF potential to Review Required.",
    "review_status": "Corrected"
}

# Log audit manually for changed fields in simulation
fields_to_audit = {
    "final_sif_label": ("ai_sif_label", "SIF Label"),
    "final_priority": ("ai_priority", "Priority")
}
for field, (ai_key, display_name) in fields_to_audit.items():
    old_val = danger_report[ai_key]
    new_val = corr_data[field]
    if old_val != new_val:
        log_audit(
            report_id=danger_report_id,
            user_name="HSE Officer Bob",
            role="HSE Officer",
            action="HSE Override",
            field_name=display_name,
            old_value=old_val,
            new_value=new_val
        )

save_hse_review(corr_data)

# Verify override persistence
corr_report = get_report_by_id(danger_report_id)
print(f"  * report_status: {corr_report['report_status']} (Expected: Corrected)")
print(f"  * final_sif_label: {corr_report['final_sif_label']} (Expected: Review Required)")
print(f"  * original ai_sif_label (unchanged): {corr_report['ai_sif_label']} (Expected: SIF-potential)")

# Check audit logs old vs new values
audit_corr = get_audit_trail(danger_report_id)
print("  * Audit Overrides details:")
for a in audit_corr:
    if a["action"] == "HSE Override":
        print(f"    - Field: {a['field_name']} | Old: {a['old_value']} | New: {a['new_value']} | User: {a['user_name']} ({a['role']})")
print("\n" + "="*50 + "\n")

# 6. Status Machine transitions
print("6. STATUS MACHINE TRANSITIONS:")
print(f"  * Pending HSE Review -> Accepted: {validate_status_transition('Pending HSE Review', 'Accepted')}")
print(f"  * Pending HSE Review -> Corrected: {validate_status_transition('Pending HSE Review', 'Corrected')}")
print(f"  * Pending HSE Review -> Duplicate: {validate_status_transition('Pending HSE Review', 'Duplicate')}")
print(f"  * Pending HSE Review -> Rejected: {validate_status_transition('Pending HSE Review', 'Rejected')}")
print(f"  * Pending HSE Review -> Action In Progress: {validate_status_transition('Pending HSE Review', 'Action In Progress')} (Expected: False)")
print(f"  * Closed -> Accepted: {validate_status_transition('Closed', 'Accepted')} (Expected: False)")
print("\n" + "="*50 + "\n")
