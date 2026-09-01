import os
import pickle
import json
from services.safety_rules import (
    analyze_safety_barriers, match_life_saving_rules, extract_structured_fields, is_negated
)
from services.llm_service import extract_safety_details

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "sif_classifier.pkl")

# Incident keywords
INCIDENT_KEYWORDS = {
    "near miss", "incident", "accident", "injury", "stopped", "prevented", "occurred", "occur", "failed", "leak", "fire"
}

def load_ml_pipeline():
    """Attempts to load the scikit-learn model pipeline from disk."""
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except:
        return None

def calculate_sif_score(text: str, barrier_findings: dict, fields: dict) -> tuple[int, dict]:
    """Calculates SIF score based on explicit evidence in the structured fields and text.
    Returns (score, score_breakdown).
    """
    cleaned_text = text.lower()
    score = 0
    breakdown = {}
    
    # 1. High-energy hazard (+2)
    if fields.get("energy_sources") != "Not identified from report" or fields.get("hazards") != "Not identified from report":
        score += 2
        breakdown["High-energy hazard detected"] = 2
        
    # 2. Person directly exposed (+3)
    if fields.get("exposure") != "Not identified from report":
        score += 3
        breakdown["Person directly exposed"] = 3
        
    # 3. Missing/failed barrier (+3)
    has_failed_barrier = len(barrier_findings.get("failed_barriers", [])) > 0
    if has_failed_barrier:
        score += 3
        breakdown["Missing/failed safety barrier detected"] = 3
        
    # 4. Credible fatal consequence (+2)
    if fields.get("potential_consequences") != "Not identified from report":
        score += 2
        breakdown["Credible fatal consequence identified"] = 2
        
    # 5. Multiple people exposed (+1)
    if "Multiple personnel" in fields.get("exposure", ""):
        score += 1
        breakdown["Multiple personnel exposed"] = 1
        
    # 6. Near-miss/incident context (+1)
    has_context = any(kw in cleaned_text for kw in INCIDENT_KEYWORDS)
    if has_context or fields.get("actual_injury") != "Not identified from report":
        score += 1
        breakdown["Near-miss or incident context matches"] = 1
        
    return score, breakdown

def compute_review_priority(sif_score: int, immediate_danger: bool, sif_label: str) -> str:
    """Calculates deterministic review priority: Critical, High, Medium, Low."""
    if immediate_danger or (sif_label == "SIF-potential" and sif_score >= 9):
        return "Critical"
    elif sif_label == "SIF-potential" or (sif_label == "Review Required" and sif_score >= 5):
        return "High"
    elif sif_label == "Review Required":
        return "Medium"
    else:
        return "Low"

def get_evidence_strength(sif_score: int) -> str:
    """Classifies SIF evidence strength."""
    if sif_score >= 7:
        return "HIGH"
    elif sif_score >= 4:
        return "MEDIUM"
    else:
        return "LOW"

def generate_explanation_text(sif_label: str, sif_score: int, priority: str, 
                               breakdown: dict, barrier_findings: dict, fields: dict) -> str:
    """Generates a structured, explainable textual breakdown of the safety findings."""
    detected = []
    if "High-energy hazard detected" in breakdown:
        detected.append(f"• High-energy hazard:\n    {fields['hazards']}")
    if "Person directly exposed" in breakdown:
        detected.append(f"• Person directly exposed:\n    {fields['exposure']}")
    if "Missing/failed safety barrier detected" in breakdown:
        failed_list = ", ".join(barrier_findings["failed_barriers"])
        detected.append(f"• Failed safety barrier:\n    {failed_list}")
    if "Credible fatal consequence identified" in breakdown:
        detected.append(f"• Credible potential consequence:\n    {fields['potential_consequences']}")
        
    detected_section = "\n\n".join(detected)
    
    score_lines = []
    for k, v in breakdown.items():
        score_lines.append(f"{k:<45} +{v}")
        
    score_section = "\n".join(score_lines)
    
    explanation = f"""WHY {sif_label.upper()}?

Detected evidence:
{detected_section if detected else "No significant safety hazards flagged."}

SIF SCORE
{score_section}
---------------------------------------------
TOTAL                                         {sif_score}

Classification:
{sif_label}

Priority:
{priority}"""
    return explanation

def classify_report(text: str, immediate_action: str = "", immediate_danger: int = 0) -> dict:
    """Performs explainable safety classification routing through the 3-layer pipeline."""
    # Layer 1: LLM Extraction
    combined_text = text
    if immediate_action:
        combined_text += f"\nImmediate action taken: {immediate_action}"
    llm_result = extract_safety_details(combined_text)
    
    if llm_result:
        fields = {
            "activity": llm_result.get("activity", "Not identified from report"),
            "hazards": llm_result.get("hazards", "Not identified from report"),
            "energy_sources": llm_result.get("energy_sources", "Not identified from report"),
            "exposure": llm_result.get("exposure", "Not identified from report"),
            "potential_consequences": llm_result.get("potential_consequences", "Not identified from report")
        }
        llm_provider = llm_result.get("llm_provider")
        llm_model = llm_result.get("llm_model")
        llm_analysis_status = llm_result.get("llm_analysis_status")
        llm_confidence = llm_result.get("llm_confidence")
        llm_reasoning = llm_result.get("llm_reasoning", "")
        actual_injury = llm_result.get("actual_injury", "Not identified from report")
        
        llm_failed_barriers = llm_result.get("failed_barrier_candidates", [])
        llm_lsr = llm_result.get("life_saving_rule_candidates", [])
        llm_evidence = llm_result.get("evidence", [])
    else:
        combined_text = text
        if immediate_action:
            combined_text += f" {immediate_action}"
        fields = extract_structured_fields(combined_text)
        llm_provider = "Regex Fallback"
        llm_model = "Rule-Engine-v1"
        llm_analysis_status = "LLM Unavailable"
        llm_confidence = 1.0
        llm_reasoning = "LLM was unavailable. Fallback regex models applied."
        actual_injury = fields.get("actual_injury", "Not identified from report")
        
        llm_failed_barriers = []
        llm_lsr = []
        llm_evidence = []
        
    # Layer 2: Rule Engine Validation & Scoring
    barrier_findings = analyze_safety_barriers(text)
    rules, rule_ev = match_life_saving_rules(text, barrier_findings)
    
    sif_score, breakdown = calculate_sif_score(text, barrier_findings, fields)
    
    # We enrich Rule Engine findings with LLM candidates if Rule Engine missed them,
    # but ONLY IF the text contains explicit evidence (Rule Engine remains authoritative for the score).
    # For now, we will merge the textual output but keep the deterministic score from calculate_sif_score.
    combined_failed_barriers = list(set(barrier_findings["failed_barriers"] + llm_failed_barriers))
    combined_lsr = list(set(rules + llm_lsr))
    combined_evidence = list(set(barrier_findings["evidence"] + rule_ev + llm_evidence))

    evidence_strength = get_evidence_strength(sif_score)
    
    # Map SIF potential from score
    if sif_score >= 7:
        rule_engine_label = "SIF-potential"
    elif sif_score >= 4:
        rule_engine_label = "Review Required"
    else:
        rule_engine_label = "Non-SIF-potential"
        
    # Layer 3: Supporting ML Classification
    pipeline = load_ml_pipeline()
    ml_prediction = None
    ml_confidence_val = None
    classifier_mode = "Hybrid AI (LLM + Rule Engine)"
    model_version = "3.0-Hybrid"
    
    if pipeline:
        try:
            pred_arr = pipeline.predict([text])
            prob_arr = pipeline.predict_proba([text])
            ml_prediction = pred_arr[0]
            ml_confidence_val = float(max(prob_arr[0]))
            classifier_mode = "Hybrid AI (LLM + Rule Engine + ML)"
        except:
            pass
            
    # Final Decision Resolution (Rule engine is authoritative for explicit safety evidence)
    if rule_engine_label == "SIF-potential":
        final_label = "SIF-potential"
    elif rule_engine_label == "Review Required" and ml_prediction == "SIF-potential":
        final_label = "SIF-potential"
    else:
        final_label = ml_prediction if ml_prediction else rule_engine_label
        
    # Priority Calculation
    priority = compute_review_priority(sif_score, bool(immediate_danger), final_label)
    
    # Explanation panel
    explanation = generate_explanation_text(
        final_label, sif_score, priority, breakdown, barrier_findings, fields
    )
    if llm_reasoning:
        explanation += f"\n\nLLM Reasoning:\n{llm_reasoning}"
    
    return {
        "sif_label": final_label,
        "sif_score": sif_score,
        "priority": priority,
        "evidence_strength": evidence_strength,
        "ml_prediction": ml_prediction,
        "ml_confidence": ml_confidence_val,
        "classifier_mode": classifier_mode,
        "model_version": model_version,
        "activity": fields["activity"],
        "hazards": fields["hazards"],
        "energy_sources": fields["energy_sources"],
        "exposure": fields["exposure"],
        "failed_barriers": combined_failed_barriers,
        "potential_consequences": fields["potential_consequences"],
        "life_saving_rules": combined_lsr,
        "evidence_phrases": combined_evidence,
        "score_breakdown": json.dumps(breakdown),
        "actual_injury": actual_injury,
        "explanation": explanation,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_analysis_status": llm_analysis_status,
        "llm_confidence": llm_confidence,
    }
