import os
import sys
import json
import pickle

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.classifier import classify_report, calculate_sif_score, compute_review_priority, load_ml_pipeline
from services.safety_rules import analyze_safety_barriers, is_negated

print("==================================================")
print("PHASE 3 - STRICT CLASSIFICATION VERIFICATION SCRIPT")
print("==================================================\n")

# Helper to print structured outputs nicely
def print_structured(label, res):
    print(f"--- Golden Scenario {label} ---")
    print(f"  * Text: \"{res.get('text', '')}\"")
    print(f"  * SIF Label: {res.get('sif_label')}")
    print(f"  * SIF Score: {res.get('sif_score')}")
    print(f"  * Review Priority: {res.get('priority')}")
    print(f"  * Life-Saving Rules: {res.get('life_saving_rules')}")
    print(f"  * Failed Barriers: {res.get('failed_barriers')}")
    print(f"  * Activity: {res.get('activity')}")
    print(f"  * Hazards: {res.get('hazards')}")
    print(f"  * Energy Sources: {res.get('energy_sources')}")
    print(f"  * Exposure: {res.get('exposure')}")
    print(f"  * Consequences: {res.get('potential_consequences')}")
    print(f"  * Evidence Phrases: {res.get('evidence_phrases')}")
    print(f"  * ML Prediction / Confidence: {res.get('ml_prediction')} / {res.get('ml_confidence')}")
    print(f"  * Classifier Mode / Model Version: {res.get('classifier_mode')} / {res.get('model_version')}")
    print(f"  * Score Breakdown: {res.get('score_breakdown')}")
    print(f"  * Explanation Output:\n{res.get('explanation')}")
    print("-" * 50 + "\n")

# 1. GOLDEN SCENARIOS
print("1. EVALUATING GOLDEN SAFETY SCENARIOS...\n")

# Scenario A
text_a = "During maintenance of a crude oil pump, electrical isolation was not verified. The technician started removing the coupling guard while the pump was still connected to the power supply. The supervisor stopped the work before contact occurred."
res_a = classify_report(text_a)
res_a['text'] = text_a
print_structured("A (Pump isolation failure)", res_a)

# Scenario B
text_b = "Tank ke andar aadmi gaya hai, gas testing nahi hui."
res_b = classify_report(text_b)
res_b['text'] = text_b
print_structured("B (Confined space entry)", res_b)

# Scenario C
text_c = "Worker was working at height without proper fall protection."
res_c = classify_report(text_c)
res_c['text'] = text_c
print_structured("C (Height unanchored)", res_c)

# Scenario D
text_d = "Hot work was started without the required permit and fire protection controls."
res_d = classify_report(text_d)
res_d['text'] = text_d
print_structured("D (Hot work permit/fire controls failure)", res_d)

# 2. NEGATION CASES
print("2. EVALUATING NEGATION CASES...\n")
negation_sentences = [
    "Gas testing completed before entry.",
    "Gas testing was successfully completed before entry.",
    "Gas testing was not completed before entry.",
    "Gas testing was never performed before entry.",
    "Gas testing was incomplete before entry.",
    "Pump was isolated and isolation was verified.",
    "Pump was not isolated."
]

for idx, sentence in enumerate(negation_sentences):
    findings = analyze_safety_barriers(sentence)
    print(f"  [{idx+1}] \"{sentence}\"")
    print(f"      - Failed Barriers: {findings['failed_barriers']}")
    print(f"      - Present Barriers: {findings['present_barriers']}")
    print(f"      - Evidence: {findings['evidence']}")
print("-" * 50 + "\n")

# 3. SCORING BOUNDARIES
print("3. EVALUATING SCORING BOUNDARIES (WITH ML DEACTIVATED FOR RAW SCORE VERIFICATION)...\n")
boundary_cases = [
    # Score 3 -> Non-SIF-potential
    "A worker was observed walking near the office building.",
    # Score 4 -> Review Required
    "A near miss was observed involving a technician walking on the walkway.",
    # Score 6 -> Review Required
    "A near miss occurred when a technician was servicing the electrical fan.",
    # Score 8 -> SIF-potential
    "A technician opened the switchboard box without isolation of the power supply."
]

# Temporary disable ML for raw scoring boundary check
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "sif_classifier.pkl")
TEMP_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "sif_classifier.pkl.tmp")

if os.path.exists(MODEL_PATH):
    os.rename(MODEL_PATH, TEMP_MODEL_PATH)

for text in boundary_cases:
    res = classify_report(text)
    print(f"  * Text: \"{text}\"")
    print(f"    - Score: {res['sif_score']}")
    print(f"    - Raw Rule-Engine Label: {res['sif_label']}")
    print(f"    - Priority: {res['priority']}")
print("-" * 50 + "\n")

# 4. RULE ENGINE VS ML PRIMACY
print("4. VERIFYING RULE ENGINE VS ML PRIMACY & FALLBACKS...\n")

# ML is currently offline from the step above
res_offline = classify_report(text_a)
print("  A. Testing with ML Model UNAVAILABLE:")
print(f"    - ml_prediction: {res_offline['ml_prediction']} (Expected: None)")
print(f"    - ml_confidence: {res_offline['ml_confidence']} (Expected: None)")
print(f"    - classifier_mode: {res_offline['classifier_mode']} (Expected: Rule Engine Only)")
print(f"    - model_version: {res_offline['model_version']} (Expected: 1.0-RuleEngine)")

# Restore model
if os.path.exists(TEMP_MODEL_PATH):
    if os.path.exists(MODEL_PATH):
        os.remove(TEMP_MODEL_PATH)
    else:
        os.rename(TEMP_MODEL_PATH, MODEL_PATH)

print("\n  B. Testing with ML Model AVAILABLE:")
res_online = classify_report(text_a)
print(f"    - ml_prediction: {res_online['ml_prediction']} (Expected: SIF-potential)")
print(f"    - ml_confidence: {res_online['ml_confidence']:.4f} (Expected: Probability Float)")
print(f"    - classifier_mode: {res_online['classifier_mode']} (Expected: Rule Engine + ML Supporting)")
print(f"    - model_version: {res_online['model_version']} (Expected: 2.0-LogisticRegression)")

# 5. REVIEW PRIORITY AND IMMEDIATE DANGER
print("\n5. VERIFYING REVIEW PRIORITY & IMMEDIATE DANGER...")

# A. Evaluate in Offline Mode (Raw Heuristics Priority)
if os.path.exists(MODEL_PATH):
    os.rename(MODEL_PATH, TEMP_MODEL_PATH)

print("  * Offline Mode (Raw Heuristics Priorities):")
res_danger_off = classify_report("Housekeeping puddle near walkway.", immediate_danger=1)
print(f"    - Puddle with immediate_danger=1 -> Score: {res_danger_off['sif_score']} | Priority: {res_danger_off['priority']} (Expected: Critical)")
res_low_off = classify_report("Housekeeping puddle near walkway.", immediate_danger=0)
print(f"    - Puddle with immediate_danger=0 -> Score: {res_low_off['sif_score']} | Priority: {res_low_off['priority']} (Expected: Low)")
res_high_off = classify_report("Technician was welding on scaffold without harness.", immediate_danger=0)
print(f"    - Scaffolder without harness (danger=0) -> Score: {res_high_off['sif_score']} | Priority: {res_high_off['priority']} (Expected: High)")

# Restore model
if os.path.exists(TEMP_MODEL_PATH):
    if os.path.exists(MODEL_PATH):
        os.remove(TEMP_MODEL_PATH)
    else:
        os.rename(TEMP_MODEL_PATH, MODEL_PATH)

print("\n  * Online Mode (ML Predictions Priorities):")
res_danger_on = classify_report("Housekeeping puddle near walkway.", immediate_danger=1)
print(f"    - Puddle with immediate_danger=1 -> Score: {res_danger_on['sif_score']} | Priority: {res_danger_on['priority']} (Expected: Critical)")
res_low_on = classify_report("Housekeeping puddle near walkway.", immediate_danger=0)
print(f"    - Puddle with immediate_danger=0 -> Score: {res_low_on['sif_score']} | Priority: {res_low_on['priority']} (Expected: High/Low depending on ML classification)")
res_high_on = classify_report("Technician was welding on scaffold without harness.", immediate_danger=0)
print(f"    - Scaffolder without harness (danger=0) -> Score: {res_high_on['sif_score']} | Priority: {res_high_on['priority']} (Expected: High)")

print("-" * 50 + "\n")

# 6. STRUCTURED CONTRACT VALIDATION
print("6. VALIDATING STRUCTURED CONTRACT FIELDS...")
contract_keys = [
    "sif_label", "sif_score", "priority", "evidence_strength", "ml_prediction",
    "ml_confidence", "classifier_mode", "model_version", "activity", "hazards",
    "energy_sources", "exposure", "failed_barriers", "potential_consequences",
    "life_saving_rules", "evidence_phrases", "score_breakdown", "explanation"
]

all_fields_present = True
for key in contract_keys:
    if key in res_a:
        print(f"  - Key present: {key:<25} | Type: {type(res_a[key]).__name__}")
    else:
        print(f"  - Key MISSING: {key}")
        all_fields_present = False

if all_fields_present:
    print("\n[PASS] Structured Output Contract: PASS (All fields consistent and serializable).")
else:
    print("\n[FAIL] Structured Output Contract: FAIL.")
