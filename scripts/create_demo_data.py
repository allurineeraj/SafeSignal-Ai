import os
import csv
import json
import random
from datetime import datetime, timedelta, timezone

# Ensure target directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("database", exist_ok=True)

# 8 Golden Scenarios
GOLDEN_SCENARIOS = [
    # 1. Pump maintenance + isolation failure -> SIF-potential
    {
        "description": "During maintenance of a crude oil pump, electrical isolation was not verified. The technician started removing the coupling guard while the pump was still connected to the power supply. The supervisor stopped the work before contact occurred.",
        "site": "Demo Refinery North",
        "location": "Crude Distillation Unit",
        "report_type": "Near Miss",
        "language": "English",
        "sif_label": "SIF-potential",
        "life_saving_rule": ["Energy Isolation", "Line of Fire"],
        "activity": "Pump maintenance",
        "hazard": "Electrical and mechanical energy",
        "failed_barrier": "Isolation not verified, Work authorisation or permit-control failure",
        "potential_consequence": "Electrocution, Crushing, Entanglement",
        "immediate_danger": 0,
        "review_priority": "Critical"
    },
    # 2. Confined-space entry + missing gas testing -> SIF-potential
    {
        "description": "Tank ke andar aadmi gaya hai, gas testing nahi hui.",
        "translated_text": "A person went inside the tank, gas testing has not been done.",
        "site": "Demo Refinery North",
        "location": "Product Storage Tank 102",
        "report_type": "Unsafe Act",
        "language": "Hindi",
        "sif_label": "SIF-potential",
        "life_saving_rule": ["Confined Space"],
        "activity": "Confined-space entry",
        "hazard": "Possible toxic or oxygen-deficient atmosphere",
        "failed_barrier": "Gas testing",
        "potential_consequence": "Asphyxiation, Toxic exposure, Fatality",
        "immediate_danger": 0,
        "review_priority": "Critical"
    },
    # 3. Working at height + failed protection -> SIF-potential
    {
        "description": "Worker was observed climbing the structural scaffold at a height of 8 meters without anchoring his safety harness lanyard.",
        "site": "Demo Gas Plant East",
        "location": "Dehydration Unit",
        "report_type": "Unsafe Act",
        "language": "English",
        "sif_label": "SIF-potential",
        "life_saving_rule": ["Working at Height"],
        "activity": "Scaffolding work",
        "hazard": "Fall from height",
        "failed_barrier": "Safety harness lanyard not anchored",
        "potential_consequence": "Fatal fall from height",
        "immediate_danger": 0,
        "review_priority": "High"
    },
    # 4. Hot work + barrier/permit failure -> SIF-potential
    {
        "description": "Welder started structural welding near the active hydrocarbon manifold without an approved hot work permit.",
        "site": "Demo Pipeline Zone West",
        "location": "Main Manifold",
        "report_type": "Unsafe Act",
        "language": "English",
        "sif_label": "SIF-potential",
        "life_saving_rule": ["Hot Work", "Work Authorisation"],
        "activity": "Welding",
        "hazard": "Ignition of hydrocarbon gas",
        "failed_barrier": "Hot work permit not approved",
        "potential_consequence": "Explosion, Fire, Severe burns",
        "immediate_danger": 0,
        "review_priority": "High"
    },
    # 5. Gas testing successfully completed -> no failed barrier
    {
        "description": "Gas testing completed before vessel entry. All oxygen and toxic levels verified within safety margins.",
        "site": "Demo Refinery North",
        "location": "Product Storage Tank 102",
        "report_type": "Unsafe Condition",
        "language": "English",
        "sif_label": "Non-SIF-potential",
        "life_saving_rule": ["Confined Space"],
        "activity": "Vessel inspection prep",
        "hazard": "None - barrier active",
        "failed_barrier": "None - gas testing verified",
        "potential_consequence": "None",
        "immediate_danger": 0,
        "review_priority": "Low"
    },
    # 6. Pump isolated and verified -> no failed barrier
    {
        "description": "Pump electrical breaker isolated and LOTO verified by supervisor prior to opening the pump casing.",
        "site": "Demo Refinery North",
        "location": "Crude Distillation Unit",
        "report_type": "Unsafe Condition",
        "language": "English",
        "sif_label": "Non-SIF-potential",
        "life_saving_rule": ["Energy Isolation"],
        "activity": "Pump repair preparation",
        "hazard": "None - barrier active",
        "failed_barrier": "None - isolation verified",
        "potential_consequence": "None",
        "immediate_danger": 0,
        "review_priority": "Low"
    },
    # 7. Low-risk housekeeping observation -> Non-SIF-potential
    {
        "description": "A small water puddle is present on the concrete walking path near the control room main entrance doors.",
        "site": "Demo Refinery North",
        "location": "Control Room Annex",
        "report_type": "Unsafe Condition",
        "language": "English",
        "sif_label": "Non-SIF-potential",
        "life_saving_rule": [],
        "activity": "Walking",
        "hazard": "Slip and trip",
        "failed_barrier": "Walkway cleaning delayed",
        "potential_consequence": "Minor sprain",
        "immediate_danger": 0,
        "review_priority": "Low"
    },
    # 8. Duplicate of Scenario 1 -> Duplicate warning
    {
        "description": "During maintenance of a crude oil pump, electrical isolation was not verified. The technician started removing the coupling guard while the pump was still connected to the power supply. The supervisor stopped the work before contact occurred.",
        "site": "Demo Refinery North",
        "location": "Crude Distillation Unit",
        "report_type": "Near Miss",
        "language": "English",
        "sif_label": "SIF-potential",
        "life_saving_rule": ["Energy Isolation", "Line of Fire"],
        "activity": "Pump maintenance",
        "hazard": "Electrical and mechanical energy",
        "failed_barrier": "Isolation not verified, Work authorisation or permit-control failure",
        "potential_consequence": "Electrocution, Crushing, Entanglement",
        "immediate_danger": 0,
        "review_priority": "Critical"
    }
]

# Generate synthetic records dynamically to reach 85 reports total
SITES = [
    "Demo Refinery North",
    "Demo Gas Plant East",
    "Demo Well Site Central",
    "Demo Pipeline Zone West"
]

LOCATIONS = {
    "Demo Refinery North": ["Crude Distillation Unit", "Product Storage Tank 102", "Maintenance Workshop B", "Compressor House"],
    "Demo Gas Plant East": ["Gas Sweetening Unit", "Control Room Annex", "LPG Loading Gantry", "Dehydration Unit"],
    "Demo Well Site Central": ["Drilling Rig floor", "Mud Pump Area", "Generator Shed", "Wellhead Xmas Tree #4"],
    "Demo Pipeline Zone West": ["Main Manifold", "Scraper Receiver Area", "Valve Station 12", "Pipeline KM 45 Corridor"]
}

demo_pool = list(GOLDEN_SCENARIOS)

additional_templates = [
    ("Energy Isolation", "Breaker lock was missing on pump motor switch during maintenance.", "LOTO failure", "Electrical shock", ["Energy Isolation"]),
    ("Confined Space", "Hole watch standby guard was absent during vessel internal inspection.", "Standby person missing", "Toxic gas or entrapment", ["Confined Space"]),
    ("Hot Work", "Grinding sparks were generated without placing fire blanket covers over LPG hoses.", "Ignition barriers missing", "Hydrocarbon fire", ["Hot Work"]),
    ("Line of Fire", "Technician stood inside the red zone hazard area near tension winch cables.", "Line of fire exposure", "Cable snap strike", ["Line of Fire"]),
    ("Working at Height", "Worker was standing on scaffold platform edge without securing safety lanyard.", "Harness unanchored", "Fall from height", ["Working at Height"]),
    ("Driving", "Forklift reversed in active loading bay without Reverse spotter present.", "Reverse spotter missing", "Pedestrian impact", ["Driving"]),
    ("Bypassing Safety Controls", "Agitator safety interlock switch was bypassed using wire bridge.", "Interlock bypassed", "Mechanical entrapment", ["Bypassing Safety Controls"]),
    ("Safe Mechanical Lifting", "Rigging crew utilized a frayed wire sling with missing test tags.", "Damaged lifting gear", "Dropped load crush", ["Safe Mechanical Lifting"]),
    ("Work Authorisation", "Started pipeline repairs inside valve pit before obtaining permit signature.", "Work permit missing", "Process gas release", ["Work Authorisation"])
]

random.seed(1234)

# Create 77 additional reports to hit 85 total
for idx in range(77):
    template = random.choice(additional_templates)
    rule_name, desc_stub, barrier, hazard, rules_list = template
    site = random.choice(SITES)
    location = random.choice(LOCATIONS[site])
    
    # 20% Non-SIF slip/housekeeping, 15% immediate danger, 50% SIF, 15% Review Req
    rand_val = random.random()
    if rand_val < 0.20:
        sif_label = "Non-SIF-potential"
        report_type = random.choice(["Unsafe Act", "Unsafe Condition"])
        desc = f"Routine observation: {desc_stub.lower()} in inactive equipment storage yard. Low threat level."
        rules_list = []
        barrier = "None"
        hazard = "Slips and trips"
        potential_consequence = "Minor scrape"
        immediate_danger = 0
        review_priority = "Low"
    elif rand_val < 0.35:
        # Immediate danger triggers
        sif_label = "SIF-potential"
        report_type = "Incident"
        desc = f"IMMEDIATE DANGER: Worker currently trapped under dropped pipe manifold. Urgent dispatch needed."
        barrier = "Lifting rigging failure"
        hazard = "Manifold collapse"
        potential_consequence = "Fatal crushing"
        immediate_danger = 1
        review_priority = "Critical"
    elif rand_val < 0.50:
        sif_label = "Review Required"
        report_type = "Unsafe Condition"
        desc = f"Audit note: observed that {desc_stub.lower()} during plant weekly tour. Needs validation."
        potential_consequence = "Moderate impact, possible injury"
        immediate_danger = 0
        review_priority = "Medium"
    else:
        sif_label = "SIF-potential"
        report_type = random.choice(["Near Miss", "Incident"])
        desc = f"Critical safety event: {desc_stub} Barrier controls failed completely."
        potential_consequence = f"Fatality due to {hazard.lower()}"
        immediate_danger = 0
        review_priority = "High"

    demo_pool.append({
        "description": desc,
        "site": site,
        "location": location,
        "report_type": report_type,
        "language": "English",
        "sif_label": sif_label,
        "life_saving_rule": rules_list,
        "activity": "Routine Operations" if sif_label != "Non-SIF-potential" else "Walking",
        "hazard": hazard,
        "failed_barrier": barrier,
        "potential_consequence": potential_consequence,
        "immediate_danger": immediate_danger,
        "review_priority": review_priority
    })

def generate_csv():
    csv_file = "data/demo_reports.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "report_id", "report_date", "site", "location", "report_type",
            "description", "language", "sif_label", "life_saving_rule",
            "activity", "hazard", "failed_barrier", "potential_consequence",
            "immediate_danger", "review_priority"
        ])
        
        base_date = datetime.now(timezone.utc) - timedelta(days=90)
        for idx, item in enumerate(demo_pool):
            report_id = 1000 + idx
            report_date = (base_date + timedelta(days=idx*1.05)).strftime("%Y-%m-%d %H:%M:%S")
            desc = item["description"]
            
            # Stringify lists
            rule_str = json.dumps(item["life_saving_rule"])
            
            writer.writerow([
                report_id, report_date, item["site"], item["location"], item["report_type"],
                desc, item["language"], item["sif_label"], rule_str,
                item["activity"], item["hazard"], item["failed_barrier"], item["potential_consequence"],
                item["immediate_danger"], item["review_priority"]
            ])
            
    print(f"Generated {len(demo_pool)} records in {csv_file}")

def seed_database():
    from database.db import init_db, get_connection
    init_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Reset database cleanly to avoid duplicate insertions
    cursor.execute("DELETE FROM reports;")
    cursor.execute("DELETE FROM ai_predictions;")
    cursor.execute("DELETE FROM hse_reviews;")
    cursor.execute("DELETE FROM corrective_actions;")
    cursor.execute("DELETE FROM audit_log;")
    
    base_date = datetime.now(timezone.utc) - timedelta(days=90)
    
    for idx, item in enumerate(demo_pool):
        report_id = idx + 1
        created_at = (base_date + timedelta(days=idx*1.05)).strftime("%Y-%m-%d %H:%M:%S")
        
        original_lang = item["language"]
        original_text = item["description"]
        translated_text = item.get("translated_text", None)
        
        source_type = "Audio File" if original_lang != "English" else "Text Input"
        audio_path = f"uploads/audio/demo_audio_{report_id}.wav" if original_lang != "English" else None
        
        # Determine status transitions flow
        status = "Pending HSE Review"
        if idx >= 75:
            # Seed some accepted and closed reports
            status = "Closed" if idx % 2 == 0 else "Accepted"
            
        cursor.execute("""
            INSERT INTO reports (
                id, created_at, report_type, site, location, original_language,
                original_text, translated_text, immediate_action, anonymous,
                submitted_on_behalf, submitted_by, audio_path, image_path,
                document_path, source_type, immediate_danger, review_priority, report_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id, created_at, item["report_type"], item["site"], item["location"],
            original_lang, original_text, translated_text,
            "Supervisor informed." if item["sif_label"] == "SIF-potential" else None,
            0, 0, None, audio_path, None, None, source_type,
            item["immediate_danger"], item["review_priority"], status
        ))
        
        # Save Predictions
        rules_json = json.dumps(item["life_saving_rule"])
        
        evidence_phrases = ["Safety analysis trigger"]
        if "isolation" in original_text.lower():
            evidence_phrases.append("Isolation keyword matched")
        if "gas testing" in original_text.lower() or "testing" in str(translated_text).lower():
            evidence_phrases.append("Gas testing barrier failed")
            
        evidence_json = json.dumps(evidence_phrases)
        
        # SIF score mapping
        score = 8 if item["sif_label"] == "SIF-potential" else (5 if item["sif_label"] == "Review Required" else 2)
        
        cursor.execute("""
            INSERT INTO ai_predictions (
                report_id, sif_label, sif_score, confidence, priority, activity,
                hazard, energy_source, exposure, failed_barrier, potential_consequence,
                life_saving_rules, evidence_phrases, classifier_mode, model_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id, item["sif_label"], score,
            None,  # Explicitly NULL since ML classifier is offline/unavailable in Phase 2
            item["review_priority"], item["activity"], item["hazard"],
            "Electrical/Mechanical" if "pump" in original_text else "None",
            "Technician" if "technician" in original_text.lower() else "Operator",
            item["failed_barrier"], item["potential_consequence"],
            rules_json, evidence_json, "Rule-engine fallback", "1.0-test", created_at
        ))
        
        # Seed HSE reviews for closed and accepted ones
        if idx >= 75:
            cursor.execute("""
                INSERT INTO hse_reviews (
                    report_id, reviewer_name, final_sif_label, final_priority, final_activity,
                    final_hazard, final_energy_source, final_exposure, final_failed_barrier,
                    final_potential_consequence, final_life_saving_rules, hse_comments, review_status, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, "HSE Reviewer", item["sif_label"], item["review_priority"],
                item["activity"], item["hazard"], "Mechanical", "Technician",
                item["failed_barrier"], item["potential_consequence"], rules_json,
                "Seeded review.", status, created_at
            ))
            
            # If Closed, also seed completed corrective actions
            if status == "Closed":
                cursor.execute("""
                    INSERT INTO corrective_actions (
                        report_id, action_plan, responsible_department, assigned_to,
                        priority, target_date, status, completion_notes, completed_at, assigned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id, "Ensure LOTO checks are in register.", "Operations", "John Operator",
                    "High", (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d"),
                    "Completed", "LOTO verification checklist updated.", created_at, created_at
                ))
            
            # Save audit logs
            cursor.execute("""
                INSERT INTO audit_log (report_id, user_name, role, action, field_name, old_value, new_value, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, "HSE Reviewer", "HSE Officer", "Create Review", None, None, None, created_at
            ))
            
    conn.commit()
    conn.close()
    print("Database successfully seeded with demo records.")

if __name__ == "__main__":
    generate_csv()
    seed_database()
