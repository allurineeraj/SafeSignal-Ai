import os
import pytest
import sqlite3
import json
from datetime import datetime, timezone

# Redirect database path to isolated test file prior to database module imports
import database.db
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_db.sqlite")
database.db.DB_PATH = TEST_DB_PATH

from database.db import (
    init_db, save_report, save_ai_prediction, save_hse_review,
    add_corrective_action, update_corrective_action_status,
    get_report_by_id, get_all_reports, get_audit_trail, get_stats,
    update_report_status, validate_status_transition, get_connection
)

@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup: Ensure tables exist
    init_db()
    
    # Truncate tables to ensure a clean starting state
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports;")
    cursor.execute("DELETE FROM ai_predictions;")
    cursor.execute("DELETE FROM hse_reviews;")
    cursor.execute("DELETE FROM corrective_actions;")
    cursor.execute("DELETE FROM audit_log;")
    conn.commit()
    conn.close()
    
    yield
    
    # Teardown: Truncate tables again
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reports;")
        cursor.execute("DELETE FROM ai_predictions;")
        cursor.execute("DELETE FROM hse_reviews;")
        cursor.execute("DELETE FROM corrective_actions;")
        cursor.execute("DELETE FROM audit_log;")
        conn.commit()
        conn.close()
    except:
        pass

# 1. Database Table Creation Verification
def test_database_table_creation():
    assert os.path.exists(TEST_DB_PATH)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row['name'] for row in cursor.fetchall()]
    conn.close()
    
    # Assert all tables exist
    assert "reports" in tables
    assert "ai_predictions" in tables
    assert "hse_reviews" in tables
    assert "corrective_actions" in tables
    assert "audit_log" in tables

# 2. Database Indexes Verification
def test_database_indexes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = [row['name'] for row in cursor.fetchall()]
    conn.close()
    
    assert "idx_reports_site" in indexes
    assert "idx_reports_type" in indexes
    assert "idx_reports_status" in indexes
    assert "idx_reports_priority" in indexes
    assert "idx_reports_created" in indexes

# 3. Foreign Key Constraint Enforcement Verification
def test_foreign_key_constraints():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys explicitly in connection
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Try inserting an AI prediction for a report ID that doesn't exist
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO ai_predictions (
                report_id, sif_label, sif_score, confidence, priority, activity,
                hazard, energy_source, exposure, failed_barrier, potential_consequence,
                life_saving_rules, evidence_phrases, classifier_mode, model_version
            ) VALUES (9999, 'SIF-potential', 10, NULL, 'Critical', 'Maintenance', 'Electricity', 'None', 'None', 'None', 'None', '[]', '[]', 'Rule-engine fallback', '1.0')
        """)
        conn.commit()
        
    conn.close()

# 4. State Machine Transition Rules Verification
def test_state_machine_transitions():
    # Test valid initial status transitions
    assert validate_status_transition(None, "Submitted")
    assert validate_status_transition(None, "Pending HSE Review")
    
    # Test invalid target status
    assert not validate_status_transition(None, "InvalidStatus")
    
    # Test standard transition paths
    assert validate_status_transition("Submitted", "Pending HSE Review")
    assert validate_status_transition("Pending HSE Review", "Accepted")
    assert validate_status_transition("Pending HSE Review", "Corrected")
    assert validate_status_transition("Accepted", "Action Assigned")
    assert validate_status_transition("Corrected", "Action Assigned")
    assert validate_status_transition("Action Assigned", "Action In Progress")
    assert validate_status_transition("Action In Progress", "Closed")
    
    # Test invalid transitions
    assert not validate_status_transition("Closed", "Pending HSE Review")
    assert not validate_status_transition("Rejected", "Accepted")
    assert not validate_status_transition("Submitted", "Closed")

# 5. DB Layer Status Transitions and Exceptions Validation
def test_report_status_db_validation():
    # Insert report
    report_id = save_report({
        "report_type": "Near Miss",
        "site": "Demo Refinery North",
        "location": "Sump Area",
        "original_language": "English",
        "original_text": "Unverified isolation on breaker board.",
        "source_type": "Text Input",
        "immediate_danger": 0,
        "review_priority": "Critical",
        "report_status": "Submitted"
    })
    
    # Trigger valid status shift
    update_report_status(report_id, "Pending HSE Review", "System", "System")
    retrieved = get_report_by_id(report_id)
    assert retrieved["report_status"] == "Pending HSE Review"
    
    # Trigger invalid status shift -> must raise ValueError
    with pytest.raises(ValueError):
        update_report_status(report_id, "Action In Progress", "System", "System")

# 6. Audit Records Verification
def test_audit_logs_creation():
    report_id = save_report({
        "report_type": "Unsafe Act",
        "site": "Demo Refinery North",
        "location": "Unit 2",
        "original_language": "English",
        "original_text": "Welding without permit.",
        "source_type": "Text Input",
        "immediate_danger": 0,
        "review_priority": "High",
        "report_status": "Pending HSE Review"
    })
    
    # Create AI prediction
    save_ai_prediction({
        "report_id": report_id,
        "sif_label": "Review Required",
        "sif_score": 5,
        "confidence": None,
        "priority": "High",
        "activity": "Welding",
        "hazard": "Gas ignition",
        "energy_source": "Chemical",
        "exposure": "Welder",
        "failed_barrier": "Permit",
        "potential_consequence": "Explosion",
        "life_saving_rules": json.dumps(["Hot Work"]),
        "evidence_phrases": json.dumps(["sparks", "no permit"]),
        "classifier_mode": "Rule-engine fallback",
        "model_version": "1.0-test"
    })
    
    # Save HSE Review
    review_data = {
        "report_id": report_id,
        "reviewer_name": "Senior HSE Inspector",
        "final_sif_label": "SIF-potential",
        "final_priority": "Critical",
        "final_activity": "Welding work",
        "final_failed_barrier": "Permit missing",
        "review_status": "Corrected"
    }
    save_hse_review(review_data)
    
    # Verify Audit logs
    audits = get_audit_trail(report_id)
    assert len(audits) > 0
    actions = [a['action'] for a in audits]
    # Check that Create Review audit logs was saved
    assert "Create Review" in actions
    assert "Update Status" in actions

# 7. Corrective Action Tracking Integration
def test_corrective_action_tracking():
    report_id = save_report({
        "report_type": "Unsafe Condition",
        "site": "Demo Refinery North",
        "location": "Zone 5",
        "original_language": "English",
        "original_text": "Frayed wire sling observed.",
        "source_type": "Text Input",
        "immediate_danger": 0,
        "review_priority": "High",
        "report_status": "Pending HSE Review"
    })
    
    # Seed review
    save_hse_review({
        "report_id": report_id,
        "reviewer_name": "Inspector A",
        "final_sif_label": "SIF-potential",
        "final_priority": "High",
        "review_status": "Accepted"
    })
    
    # Assign corrective action
    action_id = add_corrective_action({
        "report_id": report_id,
        "action_plan": "Replace lifting sling immediately.",
        "responsible_department": "Lifting Operations",
        "assigned_to": "Mr. Contractor",
        "priority": "High",
        "target_date": "2026-09-10",
        "status": "Assigned"
    })
    
    # Check status synched to Action Assigned
    rep = get_report_by_id(report_id)
    assert rep["report_status"] == "Action Assigned"
    
    # Set to In Progress
    update_corrective_action_status(action_id, "In Progress")
    rep = get_report_by_id(report_id)
    assert rep["report_status"] == "Action In Progress"
    
    # Complete action
    update_corrective_action_status(action_id, "Completed", "New certified wire sling purchased and LOTO tag applied.")
    rep = get_report_by_id(report_id)
    assert rep["report_status"] == "Closed"

# 8. Statistics Metrics Calculation Verification
def test_stats_calculations():
    # Seed reports of SIF-potential and Non-SIF
    r1 = save_report({
        "report_type": "Incident",
        "site": "Demo Refinery North",
        "location": "Unit A",
        "original_language": "English",
        "original_text": "Report 1 details",
        "source_type": "Text Input",
        "immediate_danger": 1,
        "review_priority": "Critical",
        "report_status": "Submitted"
    })
    save_ai_prediction({
        "report_id": r1,
        "sif_label": "SIF-potential",
        "sif_score": 10,
        "confidence": None,
        "priority": "Critical",
        "classifier_mode": "Rule-engine fallback",
        "model_version": "1.0-test"
    })
    
    r2 = save_report({
        "report_type": "Unsafe Act",
        "site": "Demo Refinery North",
        "location": "Unit B",
        "original_language": "English",
        "original_text": "Report 2 details",
        "source_type": "Text Input",
        "immediate_danger": 0,
        "review_priority": "Low",
        "report_status": "Submitted"
    })
    save_ai_prediction({
        "report_id": r2,
        "sif_label": "Non-SIF-potential",
        "sif_score": 1,
        "confidence": None,
        "priority": "Low",
        "classifier_mode": "Rule-engine fallback",
        "model_version": "1.0-test"
    })
    
    stats = get_stats()
    assert stats["total_reports"] == 2
    assert stats["sif_count"] == 1
    assert stats["sif_percentage"] == 50.0
    assert stats["critical_count"] == 1

# 9. Seeding Golden Scenarios Integration Test
def test_golden_dataset_seeding():
    from scripts.create_demo_data import generate_csv, seed_database
    
    # Run seed script
    generate_csv()
    seed_database()
    
    reports = get_all_reports()
    assert len(reports) >= 80  # Golden scenarios + additional random seed data
    
    # Inspect golden scenarios specifically
    # 1. Pump maintenance
    r1 = get_report_by_id(1)
    assert r1["site"] == "Demo Refinery North"
    assert "electrical isolation was not verified" in r1["original_text"]
    assert r1["review_priority"] == "Critical"
    assert r1["ai_sif_label"] == "SIF-potential"
    
    # 2. Hindi tank entry
    r2 = get_report_by_id(2)
    assert r2["original_language"] == "Hindi"
    assert r2["original_text"] == "Tank ke andar aadmi gaya hai, gas testing nahi hui."
    assert r2["review_priority"] == "Critical"
    assert r2["ai_sif_label"] == "SIF-potential"
    
    # 5. Gas testing completed (No failed barrier)
    r5 = get_report_by_id(5)
    assert r5["ai_sif_label"] == "Non-SIF-potential"
    assert "gas testing verified" in r5["ai_failed_barrier"]


# ================= PHASE 3 CORE NLP & CLASSIFICATION TESTS =================

from services.safety_rules import is_negated, analyze_safety_barriers, match_life_saving_rules
from services.classifier import classify_report, calculate_sif_score, compute_review_priority

def test_negation_checks():
    # Negative cases (barrier verified active, no failure)
    assert not is_negated("Gas testing completed.", "gas testing")
    assert not is_negated("Gas testing was successfully completed.", "gas testing")
    assert not is_negated("Pump was isolated and isolation verified.", "isolation")
    
    # Positive cases (barrier failed/negated)
    assert is_negated("Gas testing was not completed.", "gas testing")
    assert is_negated("Gas testing was never performed.", "gas testing")
    assert is_negated("Gas testing was incomplete.", "gas testing")
    assert is_negated("Work started without gas testing.", "gas testing")
    assert is_negated("Gas testing failed.", "gas testing")
    assert is_negated("Gas testing is missing.", "gas testing")
    assert is_negated("No gas testing was done.", "gas testing")
    assert is_negated("Pump was not isolated.", "isolated")
    assert is_negated("Tank entry done, gas testing nahi hui.", "gas testing")

def test_golden_scenarios_classifier():
    # 1. Pump maintenance + isolation failure
    res1 = classify_report(
        "During maintenance of a crude oil pump, electrical isolation was not verified. "
        "The technician started removing the coupling guard while the pump was still connected to the power supply. "
        "The supervisor stopped the work before contact occurred."
    )
    assert res1["sif_label"] == "SIF-potential"
    assert "Energy Isolation" in res1["life_saving_rules"]
    assert "Line of Fire" in res1["life_saving_rules"]
    assert any("isolation" in fb.lower() for fb in res1["failed_barriers"])
    assert res1["priority"] == "Critical"
    
    # 2. Confined space + missing gas testing
    res2 = classify_report("Tank ke andar aadmi gaya hai, gas testing nahi hui.")
    assert res2["sif_label"] == "SIF-potential"
    assert "Confined Space" in res2["life_saving_rules"]
    assert any("gas testing" in fb.lower() for fb in res2["failed_barriers"])
    
    # 3. Height + harness unanchored
    res3 = classify_report("Worker was observed climbing the structural scaffold at a height of 8 meters without anchoring his safety harness lanyard.")
    assert res3["sif_label"] == "SIF-potential"
    assert "Working at Height" in res3["life_saving_rules"]
    assert any("fall protection" in fb.lower() for fb in res3["failed_barriers"])
    
    # 4. Hot work + permit failure
    res4 = classify_report("Welder started structural welding near the active hydrocarbon manifold without an approved hot work permit.")
    assert res4["sif_label"] == "SIF-potential"
    assert "Hot Work" in res4["life_saving_rules"]
    assert any("work authorisation" in fb.lower() for fb in res4["failed_barriers"])

    # 5. Gas testing completed safely
    res5 = classify_report("Gas testing completed before vessel entry. All oxygen and toxic levels verified within safety margins.")
    assert res5["sif_label"] == "Non-SIF-potential"
    assert len(res5["failed_barriers"]) == 0
    
    # 6. Pump LOTO verified
    res6 = classify_report("Pump electrical breaker isolated and LOTO verified by supervisor prior to opening the pump casing.")
    assert res6["sif_label"] == "Non-SIF-potential"
    assert len(res6["failed_barriers"]) == 0

    # 7. Low-risk housekeeping
    res7 = classify_report("A small water puddle is present on the concrete walking path near the control room main entrance doors.")
    assert res7["sif_label"] == "Non-SIF-potential"
    assert res7["sif_score"] <= 3

def test_scoring_boundaries():
    # Score 3 -> Non-SIF-potential
    # Person directly exposed (+3), no other triggers
    score3, _ = calculate_sif_score("A routine operator was observed walking.", {"failed_barriers": []})
    assert score3 == 3
    
    # Score 5 -> Review Required
    # High-energy hazard (+2) + Person exposed (+3)
    score5, _ = calculate_sif_score("Technician working on scaffolding.", {"failed_barriers": []})
    assert score5 == 5
    
    # Score 8 -> SIF-potential
    # High-energy (+2) + Person exposed (+3) + Failed barrier (+3)
    score8, _ = calculate_sif_score("Technician working on scaffolding without harness.", {"failed_barriers": ["Fall protection missing/failed"]})
    assert score8 == 8

def test_ml_unavailable_fallback(monkeypatch):
    # Force ML loading to fail
    import services.classifier
    monkeypatch.setattr(services.classifier, "load_ml_pipeline", lambda: None)
    
    res = classify_report("Technician was welding inside vessel without permit.")
    assert res["ml_prediction"] is None
    assert res["ml_confidence"] is None
    assert res["classifier_mode"] == "Hybrid AI (LLM + Rule Engine)"
    assert res["model_version"] == "3.0-Hybrid"

def test_rule_engine_primacy_and_no_downgrade(monkeypatch):
    # Mock ML pipeline to return Non-SIF-potential with high confidence
    class MockPipeline:
        def predict(self, texts):
            return ["Non-SIF-potential"]
        def predict_proba(self, texts):
            return [[0.05, 0.95]] # [SIF, Non-SIF]
            
    import services.classifier
    monkeypatch.setattr(services.classifier, "load_ml_pipeline", lambda: MockPipeline())
    
    # Explicit SIF report (score >= 7)
    res = classify_report("Technician working on active crude pump without isolation LOTO.")
    
    # Rule engine must override and keep SIF-potential
    assert res["sif_score"] >= 7
    assert res["sif_label"] == "SIF-potential"
    assert res["ml_prediction"] == "Non-SIF-potential"
    assert res["ml_confidence"] == 0.95
    assert res["classifier_mode"] == "Hybrid AI (LLM + Rule Engine + ML)"

def test_review_priority_logic():
    # SIF-potential & score >= 9 -> Critical
    assert compute_review_priority(10, False, "SIF-potential") == "Critical"
    
    # SIF-potential & score < 9 -> High
    assert compute_review_priority(8, False, "SIF-potential") == "High"
    
    # Review Required & score >= 5 -> High
    assert compute_review_priority(5, False, "Review Required") == "High"
    
    # Review Required & score < 5 -> Medium
    assert compute_review_priority(4, False, "Review Required") == "Medium"
    
    # Non-SIF-potential -> Low
    assert compute_review_priority(2, False, "Non-SIF-potential") == "Low"
    
    # Immediate danger -> Critical (regardless of SIF potential or score)
    assert compute_review_priority(1, True, "Non-SIF-potential") == "Critical"

def test_explanation_generation():
    res = classify_report("Technician started welding inside confined tank without a work permit or gas testing.")
    assert "WHY SIF-POTENTIAL?" in res["explanation"].upper()
    assert "toxic" in res["explanation"].lower() or "asphyxiation" in res["explanation"].lower() or "flammable" in res["explanation"].lower()
    assert "TOTAL" in res["explanation"]
    assert "Classification:" in res["explanation"]

