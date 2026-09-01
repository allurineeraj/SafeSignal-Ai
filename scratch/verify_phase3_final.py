import os
import sys
import json
import pickle

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.classifier import classify_report, calculate_sif_score, compute_review_priority
from services.safety_rules import analyze_safety_barriers, is_negated

print("==================================================")
print("PHASE 3 - FINAL VERIFICATION OUTPUTS")
print("==================================================\n")

# A. 10 TARGET TEXTS
texts = [
    # 1
    "During pump maintenance, electrical isolation was not verified. The technician began removing the coupling guard while the pump was still connected to power.",
    # 2
    "Tank ke andar aadmi gaya hai, gas testing nahi hui.",
    # 3
    "Worker was working at height without proper fall protection.",
    # 4
    "Hot work was started without the required permit and fire protection controls.",
    # 5
    "Gas testing completed before entry.",
    # 6
    "Gas testing was successfully completed before entry.",
    # 7
    "Gas testing was not completed before entry.",
    # 8
    "Gas testing was never performed before entry.",
    # 9
    "Pump was isolated and isolation was verified.",
    # 10
    "Pump was not isolated."
]

print("A. ACTUAL CLASSIFIER OUTPUTS FOR 10 TEXTS:")
for idx, text in enumerate(texts):
    res = classify_report(text)
    print(f"\n[{idx+1}] Text: \"{text}\"")
    print(f"  - sif_label: {res.get('sif_label')}")
    print(f"  - sif_score: {res.get('sif_score')}")
    print(f"  - priority: {res.get('priority')}")
    print(f"  - evidence_strength: {res.get('evidence_strength')}")
    print(f"  - activity: {res.get('activity')}")
    print(f"  - hazards: {res.get('hazards')}")
    print(f"  - energy_sources: {res.get('energy_sources')}")
    print(f"  - exposure: {res.get('exposure')}")
    print(f"  - failed_barriers: {res.get('failed_barriers')}")
    print(f"  - potential_consequences: {res.get('potential_consequences')}")
    print(f"  - life_saving_rules: {res.get('life_saving_rules')}")
    print(f"  - evidence_phrases: {res.get('evidence_phrases')}")
    print(f"  - score_breakdown: {res.get('score_breakdown')}")
    print(f"  - ml_prediction: {res.get('ml_prediction')}")
    print(f"  - ml_confidence: {res.get('ml_confidence')}")
    print(f"  - classifier_mode: {res.get('classifier_mode')}")
    print(f"  - model_version: {res.get('model_version')}")
    print(f"  - explanation (First 6 lines):")
    lines = res.get('explanation', '').split('\n')
    for line in lines[:6]:
        print(f"      {line}")
print("\n" + "="*50 + "\n")

# B. NEGATION CHECK
print("B. NEGATION CHECKS:")
neg_checks = [
    ("Gas testing completed before entry.", False, "Gas testing"),
    ("Gas testing was successfully completed before entry.", False, "Gas testing"),
    ("Gas testing was not completed before entry.", True, "Gas testing"),
    ("Gas testing was never performed before entry.", True, "Gas testing"),
    ("Pump was isolated and isolation was verified.", False, "Energy isolation"),
    ("Pump was not isolated.", True, "Energy isolation")
]

for sentence, expected_failed, barrier_name in neg_checks:
    findings = analyze_safety_barriers(sentence)
    is_failed = any(barrier_name.lower() in fb.lower() for fb in findings["failed_barriers"])
    print(f"  * \"{sentence}\"")
    print(f"    - Has failed {barrier_name} barrier? {is_failed} (Expected: {expected_failed})")
print("\n" + "="*50 + "\n")

# C. CONJUNCTION CASE
print("C. TESTING DIFFICULT CONJUNCTION CASE:")
conj_text = "LOTO was not verified although the permit was active and the helmet was worn."
res_conj = classify_report(conj_text)
print(f"  * Text: \"{conj_text}\"")
print(f"  * Failed Barriers: {res_conj['failed_barriers']}")
print(f"  * Life-Saving Rules matched: {res_conj['life_saving_rules']}")
print(f"  * SIF Score: {res_conj['sif_score']}")
print("\n" + "="*50 + "\n")

# D. ML FALLBACK
print("D. TESTING ML FALLBACK OPERATIONS:")
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "sif_classifier.pkl")
TEMP_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "sif_classifier.pkl.tmp")

# Rename model to simulate offline fallback
if os.path.exists(MODEL_PATH):
    os.rename(MODEL_PATH, TEMP_MODEL_PATH)
    
res_off = classify_report(texts[0])
print("  * ML Model UNAVAILABLE (Offline Mode):")
print(f"    - SIF Label: {res_off['sif_label']}")
print(f"    - ml_prediction: {res_off['ml_prediction']} (Expected: None)")
print(f"    - ml_confidence: {res_off['ml_confidence']} (Expected: None)")
print(f"    - classifier_mode: {res_off['classifier_mode']} (Expected: Rule Engine Only)")

# Restore model
if os.path.exists(TEMP_MODEL_PATH):
    if os.path.exists(MODEL_PATH):
        os.remove(TEMP_MODEL_PATH)
    else:
        os.rename(TEMP_MODEL_PATH, MODEL_PATH)

res_on = classify_report(texts[0])
print("\n  * ML Model AVAILABLE (Online Mode):")
print(f"    - SIF Label: {res_on['sif_label']}")
print(f"    - ml_prediction: {res_on['ml_prediction']} (Expected: SIF-potential)")
print(f"    - ml_confidence: {res_on['ml_confidence']} (Expected: float)")
print(f"    - classifier_mode: {res_on['classifier_mode']} (Expected: Rule Engine + ML Supporting)")
print("\n" + "="*50 + "\n")

# E. SCORE INTEGRITY & BOUNDARIES
print("E. SCORE INTEGRITY & BOUNDARIES:")
boundaries = [
    ("A worker was observed walking near the office building.", 3, "Non-SIF-potential"),
    ("A near miss was observed involving a technician walking on the walkway.", 4, "Review Required"),
    ("A near miss occurred when a technician was servicing the electrical fan.", 6, "Review Required"),
    ("A technician opened the switchboard box without isolation of the power supply.", 8, "SIF-potential")
]

# Disable ML for raw score boundary check
if os.path.exists(MODEL_PATH):
    os.rename(MODEL_PATH, TEMP_MODEL_PATH)

for text, expected_score, expected_label in boundaries:
    res = classify_report(text)
    score = res['sif_score']
    breakdown = json.loads(res['score_breakdown'])
    breakdown_sum = sum(breakdown.values())
    sums_ok = score == breakdown_sum
    print(f"  * Text: \"{text}\"")
    print(f"    - Score / Breakdown Sum: {score} / {breakdown_sum} | Matches? {sums_ok}")
    print(f"    - Label / Expected: {res['sif_label']} / {expected_label}")
    
# Restore model
if os.path.exists(TEMP_MODEL_PATH):
    if os.path.exists(MODEL_PATH):
        os.remove(TEMP_MODEL_PATH)
    else:
        os.rename(TEMP_MODEL_PATH, MODEL_PATH)
print("\n" + "="*50 + "\n")
