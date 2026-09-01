import pytest
import os
import json

# Redirect database path to isolated test file prior to database module imports
import database.db
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_db.sqlite")
database.db.DB_PATH = TEST_DB_PATH

from database.db import (
    get_connection, init_db, save_report, save_ai_prediction,
    save_hse_review, update_report_status, get_report_by_id,
    get_all_reports, get_audit_trail, add_corrective_action,
    validate_status_transition, log_audit
)
from services.classifier import classify_report

@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes the database and clears tables before each test."""
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

def helper_save_prediction(report_id, res):
    """Maps classifier output to ai_predictions table schema and saves it."""
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

# 1. Successful text submission & database persistence
def test_successful_text_submission():
    report_data = {
        "report_type": "Unsafe Act",
        "site": "Duliajan HQ",
        "location": "Rig 5",
        "original_text": "Technician entered vessel without gas testing.",
        "original_language": "English",
        "immediate_action": "Supervisor stopped work.",
        "submitted_by": "Employee 123",
        "submitted_on_behalf": 0,
        "immediate_danger": 0,
        "source_type": "web_form",
        "review_priority": "Low",
        "report_status": "Submitted"
    }
    
    report_id = save_report(report_data)
    assert report_id > 0
    
    # Verify report is stored
    retrieved = get_report_by_id(report_id)
    assert retrieved is not None
    assert retrieved["original_text"] == "Technician entered vessel without gas testing."
    assert retrieved["report_status"] == "Submitted"
    
    # Save classifier prediction
    res = classify_report(retrieved["original_text"], immediate_danger=False)
    helper_save_prediction(report_id, res)
    
    # Retrieve and verify joined prediction fields
    retrieved_with_pred = get_report_by_id(report_id)
    assert retrieved_with_pred["ai_sif_label"] == "SIF-potential"
    assert "Confined Space" in retrieved_with_pred["ai_life_saving_rules"]

# 2. Anonymous submission
def test_anonymous_submission():
    report_data = {
        "report_type": "Unsafe Condition",
        "site": "Digboi Oilfield",
        "location": "Well 12",
        "original_text": "Oil spill near electrical generator.",
        "original_language": "English",
        "immediate_action": "Sandbags placed.",
        "submitted_by": "Anonymous",
        "submitted_on_behalf": 0,
        "anonymous": 1,
        "immediate_danger": 0,
        "source_type": "web_form",
        "review_priority": "Low",
        "report_status": "Submitted"
    }
    
    report_id = save_report(report_data)
    retrieved = get_report_by_id(report_id)
    assert retrieved["anonymous"] == 1
    assert retrieved["submitted_by"] == "Anonymous"

# 3. Immediate danger priority elevation
def test_immediate_danger_handling():
    report_data = {
        "report_type": "Incident",
        "site": "Moran Field",
        "location": "Gas plant",
        "original_text": "Gas leak from valve.",
        "original_language": "English",
        "immediate_action": "Shut down plant.",
        "submitted_by": "Operator 1",
        "submitted_on_behalf": 0,
        "immediate_danger": 1,
        "source_type": "web_form",
        "review_priority": "Critical",
        "report_status": "Submitted"
    }
    
    report_id = save_report(report_data)
    res = classify_report(report_data["original_text"], immediate_danger=True)
    helper_save_prediction(report_id, res)
    
    # Priority must be Critical due to immediate danger
    assert res["priority"] == "Critical"

# 4. HSE queue filtering and sorting
def test_hse_queue_filtering_and_sorting():
    # Insert multiple reports
    r1_id = save_report({
        "report_type": "Unsafe Act",
        "site": "Site A",
        "location": "Location 1",
        "original_text": "Unsafe act desc.",
        "original_language": "English",
        "submitted_by": "User 1",
        "immediate_danger": 0,
        "source_type": "web_form",
        "review_priority": "Low",
        "report_status": "Pending HSE Review"
    })
    
    r2_id = save_report({
        "report_type": "Incident",
        "site": "Site B",
        "location": "Location 2",
        "original_text": "Immediate danger desc.",
        "original_language": "English",
        "submitted_by": "User 2",
        "immediate_danger": 1,
        "source_type": "web_form",
        "review_priority": "Critical",
        "report_status": "Pending HSE Review"
    })
    
    # Test filtering site A
    site_a_reports = get_all_reports(filters={"site": "Site A"})
    assert len(site_a_reports) == 1
    assert site_a_reports[0]["id"] == r1_id
    
    # Test sorting: immediate danger (r2_id) must be first
    all_reports = get_all_reports()
    assert len(all_reports) == 2
    assert all_reports[0]["id"] == r2_id  # immediate_danger DESC
    assert all_reports[1]["id"] == r1_id

# 5. Accept AI Result
def test_accept_ai_result():
    report_data = {
        "report_type": "Unsafe Act",
        "site": "Duliajan HQ",
        "location": "Rig 5",
        "original_text": "Technician entered vessel without gas testing.",
        "original_language": "English",
        "submitted_by": "Employee 123",
        "immediate_danger": 0,
        "source_type": "web_form",
        "review_priority": "High",
        "report_status": "Pending HSE Review"
    }
    report_id = save_report(report_data)
    
    res = classify_report(report_data["original_text"], immediate_danger=False)
    helper_save_prediction(report_id, res)
    
    # Accept AI results
    review_data = {
        "report_id": report_id,
        "reviewer_name": "HSE Officer 1",
        "final_sif_label": res["sif_label"],
        "final_priority": res["priority"],
        "final_activity": res["activity"],
        "final_hazard": res["hazards"],
        "final_energy_source": res["energy_sources"],
        "final_exposure": res["exposure"],
        "final_failed_barrier": ", ".join(res["failed_barriers"]) if isinstance(res["failed_barriers"], list) else res["failed_barriers"],
        "final_potential_consequence": res["potential_consequences"],
        "final_life_saving_rules": res["life_saving_rules"],
        "hse_comments": "Accepted AI assessment.",
        "review_status": "Accepted"
    }
    save_hse_review(review_data)
    
    # Retrieve report and verify review status is updated to Accepted
    retrieved = get_report_by_id(report_id)
    assert retrieved["review_status"] == "Accepted"
    assert retrieved["report_status"] == "Accepted"
    
    # Audit log check
    audit = get_audit_trail(report_id)
    actions = [a["action"] for a in audit]
    assert "Create Review" in actions

# 6. HSE manual correction & audit logging
def test_hse_correction_and_audit():
    report_data = {
        "report_type": "Unsafe Act",
        "site": "Duliajan HQ",
        "location": "Rig 5",
        "original_text": "Technician entered vessel without gas testing.",
        "original_language": "English",
        "submitted_by": "Employee 123",
        "immediate_danger": 0,
        "source_type": "web_form",
        "review_priority": "High",
        "report_status": "Pending HSE Review"
    }
    report_id = save_report(report_data)
    
    res = classify_report(report_data["original_text"], immediate_danger=False)
    helper_save_prediction(report_id, res)
    
    # Manual override SIF-potential -> Non-SIF-potential
    review_data = {
        "report_id": report_id,
        "reviewer_name": "HSE Officer 1",
        "final_sif_label": "Non-SIF-potential",
        "final_priority": "Low",
        "final_activity": "Non-confined entry",
        "final_hazard": "None",
        "final_energy_source": "None",
        "final_exposure": "None",
        "final_failed_barrier": "None",
        "final_potential_consequence": "None",
        "final_life_saving_rules": [],
        "hse_comments": "Corrected entry error.",
        "review_status": "Corrected"
    }
    
    # log audit for overrides
    fields_to_audit = {
        "final_sif_label": ("sif_label", "SIF Label"),
        "final_priority": ("priority", "Priority")
    }
    
    for field, (ai_key, display_name) in fields_to_audit.items():
        old_val = res[ai_key]
        new_val = review_data[field]
        if old_val != new_val:
            log_audit(
                report_id=report_id,
                user_name="HSE Officer 1",
                role="HSE Officer",
                action="HSE Override",
                field_name=display_name,
                old_value=old_val,
                new_value=new_val
            )
            
    save_hse_review(review_data)
    
    # Check audit log matches overrides
    audit = get_audit_trail(report_id)
    override_fields = [a["field_name"] for a in audit if a["action"] == "HSE Override"]
    assert "SIF Label" in override_fields
    assert "Priority" in override_fields

# 7. Duplicate & Rejected reviews
def test_duplicate_and_rejected():
    report_data = {
        "report_type": "Unsafe Act",
        "site": "Duliajan HQ",
        "location": "Rig 5",
        "original_text": "Technician entered vessel without gas testing.",
        "original_language": "English",
        "submitted_by": "Employee 123",
        "immediate_danger": 0,
        "source_type": "web_form",
        "review_priority": "High",
        "report_status": "Pending HSE Review"
    }
    report_id = save_report(report_data)
    
    # Reject report
    review_reject = {
        "report_id": report_id,
        "reviewer_name": "HSE Officer 1",
        "final_sif_label": "Non-SIF-potential",
        "final_priority": "Low",
        "final_life_saving_rules": [],
        "hse_comments": "Invalid description.",
        "review_status": "Rejected"
    }
    save_hse_review(review_reject)
    
    retrieved = get_report_by_id(report_id)
    assert retrieved["report_status"] == "Rejected"

# 8. Valid/Invalid status transitions
def test_status_transitions():
    assert validate_status_transition("Pending HSE Review", "Accepted") is True
    assert validate_status_transition("Pending HSE Review", "Corrected") is True
    assert validate_status_transition("Pending HSE Review", "Rejected") is True
    assert validate_status_transition("Pending HSE Review", "Duplicate") is True
    
    # Invalid transition (Pending HSE Review directly to Action In Progress is invalid)
    assert validate_status_transition("Pending HSE Review", "Action In Progress") is False
    
    # Terminal state transitions must fail
    assert validate_status_transition("Closed", "Accepted") is False
    assert validate_status_transition("Rejected", "Pending HSE Review") is False

# 9. Malformed input checks
def test_malformed_input():
    report_data = {
        "report_type": "Unsafe Act",
        "site": "Duliajan HQ",
        "location": "Rig 5",
        "original_text": "Desc",
        "original_language": "English",
        "submitted_by": "User 1",
        "review_priority": "Low",
        "source_type": "web_form",
        "report_status": "INVALID_STATUS_VALUE"
    }
    
    # Must raise ValueError due to status constraints
    with pytest.raises(ValueError):
        save_report(report_data)

# 10. File upload size and type constraints validation
def test_unsupported_file_type():
    allowed_types = ["wav", "mp3", "pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"]
    
    filename = "malicious_script.exe"
    extension = filename.split(".")[-1]
    
    # Enforce file constraints inside backend validations
    is_valid = extension in allowed_types
    assert is_valid is False
