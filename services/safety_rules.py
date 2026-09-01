import os
import re
import json

RULES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "life_saving_rules.json")

# Improved mappings to handle real-world variations
ACTIVITY_MAP = {
    r"\bpump\b.*\bmaintenance\b|\bmaintenance\b.*\bpump\b|\bpump\b.*\brepair\b": "Pump maintenance",
    r"\btank\b.*\bentry\b|\bvessel\b.*\bentry\b|\benter\b.*\btank\b|\binside\b.*\btank\b": "Confined-space entry",
    r"\bwelding\b|\bweld\b|\bgrinding\b|\bcutting\b": "Hot work activity",
    r"\bheight\b|\bscaffold\b|\bladder\b": "Working at height",
    r"\bdriving\b|\bvehicle\b|\bforklift\b|\bcrane\b": "Vehicle/Lifting operations",
    r"\bgenerator\b.*\binspection\b|\binspection\b.*\bgenerator\b|\bgenerator\b.*\boperation\b": "Diesel generator inspection",
    r"\bmaintenance\b|\binspection\b|\brepair\b": "Maintenance / Inspection"
}

HAZARD_MAP = {
    r"\belectrical\b|\bpower supply\b|\belectricity\b|\bwire\b|\blive conductor\b": "Electrical energy",
    r"\bmechanical\b|\bcoupling\b|\bmoving parts\b|\bgear\b": "Mechanical energy",
    r"\btank\b|\bvessel\b|\bgas\b|\btoxic\b|\boxygen\b": "Toxic/flammable atmosphere",
    r"\bheight\b|\bscaffold\b|\bladder\b|\bfall\b": "Working at height fall risk",
    r"\bsuspended load\b|\blifting\b|\bcrane\b": "Suspended load impact",
    r"\bfuel leak\b|\bleaking.*hose\b|\bleak\b.*\bfuel\b": "Fuel leak / flammable substance",
    r"\bhot.*surface\b|\bhot engine\b": "Hot surface / thermal hazard"
}

ENERGY_MAP = {
    r"\belectrical\b|\bpower supply\b|\belectricity\b|\bwire\b": "Electrical",
    r"\bmechanical\b|\bcoupling\b|\bmoving parts\b|\bgear\b|\bpump\b|\bgenerator\b|\bengine\b": "Mechanical",
    r"\btank\b|\bvessel\b|\bgas\b|\btoxic\b|\boxygen\b|\bflammable\b|\bfuel\b|\bdiesel\b": "Chemical/Combustible",
    r"\bheight\b|\bscaffold\b|\bladder\b|\bfall\b|\bgravity\b": "Potential/Gravity",
    r"\bhot\b|\bthermal\b|\bburn\b": "Thermal"
}

EXPOSURE_MAP = {
    r"\btechnician\b|\bmechanic\b": "Technician directly exposed",
    r"\bwelder\b": "Welder directly exposed",
    r"\boperator\b": "Operator directly exposed",
    r"\bworker\b|\bperson\b|\baadmi\b|\bpersonnel\b": "Worker/Personnel exposed",
    r"\bcrew\b|\bteam\b|\bworkers\b": "Multiple personnel exposed"
}

CONSEQUENCE_MAP = {
    r"\belectrical\b|\belectrocution\b|\bshock\b": "Electrocution",
    r"\bcrushing\b|\bcrushed\b|\bentanglement\b|\bpinch\b": "Crushing / Entanglement",
    r"\basphyxiation\b|\bsuffocation\b|\btoxic inhalation\b": "Asphyxiation / Toxic inhalation",
    r"\bfall\b": "Fatal fall from height",
    r"\bexplosion\b|\bfire\b|\bburns\b": "Fire, explosion, or severe burns"
}

INJURY_MAP = {
    r"\bno injury\b|\bno contact\b|\bno incident\b|\bnear miss\b|\bprevented\b": "No injury reported",
    r"\bfatal\b|\bdeath\b": "Fatality",
    r"\bburn\b|\bburns\b|\bshock\b|\bcrush\b|\bfracture\b": "Injury occurred"
}

BARRIERS = {
    "Gas testing": ["gas test", "gas testing", "oxygen level", "oxygen test", "gas monitor", "gas monitoring"],
    "Energy isolation": ["isolation", "isolated", "loto", "lockout", "tagout", "breaker isolated", "de-energize", "isolated immediately"],
    "Fall protection": ["harness", "lanyard", "fall protection", "fall arrest", "scaffold guardrail"],
    "Work authorisation": ["permit", "work permit", "jsa", "job safety analysis", "authorisation", "authorization", "ptw"],
    "Standby person": ["standby person", "standby guard", "hole watch"],
    "Equipment guard": ["coupling guard", "guard removed", "interlock", "safety guard"],
    "Fire watch": ["fire watch", "fire blanket", "spark shield"]
}

# Add reverse mappings from barriers to LSR for intelligent inference
BARRIER_TO_LSR = {
    "Energy isolation": "Energy Isolation",
    "Fall protection": "Working at Height",
    "Gas testing": "Confined Space",
    "Work authorisation": "Work Authorisation",
    "Fire watch": "Hot Work",
    "Equipment guard": "Bypassing Safety Controls"
}

def load_rules() -> list[dict]:
    if not os.path.exists(RULES_JSON_PATH):
        return []
    try:
        with open(RULES_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def clean_and_tokenize(text: str) -> list[str]:
    sentences = re.split(r'[.!?\n]+', text)
    return [s.strip() for s in sentences if s.strip()]

def is_negated(text: str, target_phrase: str) -> bool:
    """Robust context-aware negation handling."""
    cleaned_text = text.lower()
    target = target_phrase.lower()
    
    if target not in cleaned_text:
        return False
        
    sentences = clean_and_tokenize(cleaned_text)
    for sentence in sentences:
        if target not in sentence:
            continue
            
        # Explicit negation phrases before the target (up to 3 words before)
        negation_prefix = r"\b(not|never|no|without|failed to|unable to|missing|lacking|wasn't|was not|had not|did not|could not)\b(?:\s+\w+){0,3}\s+" + re.escape(target)
        if re.search(negation_prefix, sentence):
            return True
            
        # Target followed by failure terms
        negation_postfix = re.escape(target) + r"(?:\s+\w+){0,3}\s+\b(missing|failed|not found|not done|not completed)\b"
        if re.search(negation_postfix, sentence):
            return True
            
    return False

def analyze_safety_barriers(text: str) -> dict:
    failed_barriers = []
    present_barriers = []
    evidence = []
    
    cleaned_text = text.lower()
    
    for barrier_name, keywords in BARRIERS.items():
        matched_keyword = None
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, cleaned_text):
                # Ensure we get the longest match if multiple apply
                if matched_keyword is None or len(kw) > len(matched_keyword):
                    matched_keyword = kw
                
        if matched_keyword:
            if is_negated(text, matched_keyword):
                failed_barriers.append(f"{barrier_name} missing/failed")
                evidence.append(f"Failed barrier: '{matched_keyword}' negated in text")
            else:
                present_barriers.append(f"{barrier_name} verified")
                evidence.append(f"Active barrier: '{matched_keyword}' matched without negation")
                
    return {
        "failed_barriers": failed_barriers,
        "present_barriers": present_barriers,
        "evidence": evidence
    }

def extract_structured_fields(text: str) -> dict:
    cleaned_text = text.lower()
    
    res = {
        "activity": "Not identified from report",
        "hazards": "Not identified from report",
        "energy_sources": "Not identified from report",
        "exposure": "Not identified from report",
        "potential_consequences": "Not identified from report",
        "actual_injury": "Not identified from report"
    }
    
    # 1. Activity
    for pattern, name in ACTIVITY_MAP.items():
        if re.search(pattern, cleaned_text):
            res["activity"] = name
            break
            
    # 2. Hazards
    matched_hazards = []
    for pattern, name in HAZARD_MAP.items():
        if re.search(pattern, cleaned_text):
            matched_hazards.append(name)
    if matched_hazards:
        res["hazards"] = ", ".join(matched_hazards)
        
    # 3. Energy Sources
    matched_energy = []
    for pattern, name in ENERGY_MAP.items():
        if re.search(pattern, cleaned_text):
            matched_energy.append(name)
    if matched_energy:
        # Avoid duplicates like multiple "Electrical" matches
        res["energy_sources"] = ", ".join(list(dict.fromkeys(matched_energy)))
        
    # 4. Exposure
    for pattern, name in EXPOSURE_MAP.items():
        if re.search(pattern, cleaned_text):
            res["exposure"] = name
            break
            
    # 5. Potential Consequences
    matched_consequences = []
    for pattern, name in CONSEQUENCE_MAP.items():
        if re.search(pattern, cleaned_text):
            matched_consequences.append(name)
    if matched_consequences:
        res["potential_consequences"] = ", ".join(list(dict.fromkeys(matched_consequences)))
        
    # 6. Actual Injury
    for pattern, name in INJURY_MAP.items():
        if re.search(pattern, cleaned_text):
            res["actual_injury"] = name
            break
            
    return res

def match_life_saving_rules(text: str, barrier_findings: dict = None) -> tuple[list[str], list[str]]:
    rules = load_rules()
    matched_rules = []
    evidence = []
    
    cleaned_text = text.lower()
    
    # Check explicit keywords
    for r in rules:
        rule_name = r["rule_name"]
        keywords = r.get("keywords", [])
        
        matched_kws = []
        for kw in keywords:
            pattern = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern, cleaned_text):
                matched_kws.append(kw)
                
        if matched_kws:
            if rule_name not in matched_rules:
                matched_rules.append(rule_name)
                evidence.append(f"Rule '{rule_name}' triggered by keyword(s): {', '.join(matched_kws)}")
                
    # Check inferred LSRs from failed barriers (intelligently map barrier failures to LSR violations)
    if barrier_findings:
        for fb in barrier_findings.get("failed_barriers", []):
            base_barrier = fb.replace(" missing/failed", "")
            if base_barrier in BARRIER_TO_LSR:
                inferred_lsr = BARRIER_TO_LSR[base_barrier]
                if inferred_lsr not in matched_rules:
                    matched_rules.append(inferred_lsr)
                    evidence.append(f"Rule '{inferred_lsr}' inferred from missing/failed safety barrier: '{base_barrier}'")
            
    return matched_rules, evidence
