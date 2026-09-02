import sys
import os
import uuid
import json
import hashlib
import binascii
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Load env variables for local testing
load_dotenv()

# Add the project root to the python path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from services.classifier import classify_report
import google.generativeai as genai
from supabase import create_client, Client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# AUTHENTICATION
# ==========================================
class LoginRequest(BaseModel):
    user_id: str
    password: str

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt_hex, pw_hash_hex = hashed_password.split(':')
        salt = binascii.unhexlify(salt_hex)
        pw_hash = binascii.unhexlify(pw_hash_hex)
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000) == pw_hash
    except Exception:
        return False

@app.post("/api/login")
async def login(req: LoginRequest):
    if not supabase:
        # Fallback demo login if no DB
        if req.user_id == "HSE001" and req.password == "HSE@1234":
            return {"success": True, "token": "demo-token", "role": "HSE Officer"}
        raise HTTPException(status_code=401, detail="Invalid credentials")

    res = supabase.table("users").select("*").eq("user_id", req.user_id).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = res.data[0]
    
    # If using db.py hash format
    if verify_password(req.password, user["password_hash"]) or (req.password == "HSE@1234" and req.user_id == "HSE001"):
        return {"success": True, "token": "demo-token-123", "role": user["role"], "user_id": user["user_id"]}
    
    # Simple plain check fallback for demo
    if req.password == user["password_hash"]:
        return {"success": True, "token": "demo-token-123", "role": user["role"], "user_id": user["user_id"]}

    raise HTTPException(status_code=401, detail="Invalid credentials")


# ==========================================
# WORKER PIPELINE
# ==========================================
class SubmitReportRequest(BaseModel):
    original_text: str
    translated_text: str
    language: str

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form(...)):
    audio_bytes = await audio.read()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
        
    try:
        genai.configure(api_key=api_key)
        
        # 1. Speech to Text
        stt_prompt = f"Transcribe this audio in its original language ({language}). Provide ONLY the transcription, no extra text."
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        stt_response = model.generate_content(
            [
                {"mime_type": audio.content_type or "audio/webm", "data": audio_bytes},
                stt_prompt
            ]
        )
        
        original_text = stt_response.text.strip()
        if not original_text:
            raise ValueError("Transcription failed")
            
        # 2. Translation to English
        translated_text = original_text
        if language != "English":
            trans_prompt = f"Translate the following {language} text to English. Provide ONLY the translation:\n\n{original_text}"
            trans_response = model.generate_content(trans_prompt)
            translated_text = trans_response.text.strip()
            
        return {
            "original_text": original_text,
            "translated_text": translated_text,
            "language": language
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit_report")
async def submit_report(req: SubmitReportRequest):
    try:
        classification = classify_report(req.translated_text)
        report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
        
        report_data = {
            "report_id": report_id,
            "report_type": "Voice",
            "site": "Demo Site",
            "location": "Unknown",
            "original_text": req.original_text,
            "original_language": req.language,
            "translated_text": req.translated_text,
            "report_status": "Pending HSE Review",
            "review_priority": classification.get("priority", "Low"),
            "immediate_danger": 0
        }
        
        prediction_data = {
            "report_id": report_id,
            "sif_label": classification.get("sif_label"),
            "sif_score": classification.get("sif_score"),
            "priority": classification.get("priority"),
            "activity": classification.get("activity"),
            "hazard": classification.get("hazards"),
            "energy_source": classification.get("energy_sources"),
            "exposure": classification.get("exposure"),
            "failed_barrier": ", ".join(classification.get("failed_barriers", [])),
            "potential_consequence": classification.get("potential_consequences"),
            "life_saving_rules": json.dumps(classification.get("life_saving_rules", [])),
            "evidence_phrases": json.dumps(classification.get("evidence_phrases", [])),
            "actual_injury": classification.get("actual_injury"),
            "explanation": classification.get("explanation"),
            "llm_provider": classification.get("llm_provider"),
            "llm_model": classification.get("llm_model"),
            "llm_analysis_status": classification.get("llm_analysis_status"),
            "llm_confidence": classification.get("llm_confidence"),
            "classifier_mode": classification.get("classifier_mode"),
            "model_version": classification.get("model_version")
        }
        
        if supabase:
            supabase.table("reports").insert(report_data).execute()
            supabase.table("ai_predictions").insert(prediction_data).execute()
            
        return {"success": True, "report_id": report_id, **report_data, **prediction_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# HSE QUEUE
# ==========================================
@app.get("/api/queue")
async def get_queue():
    if not supabase: return []
    # Fetch pending reports with their AI predictions
    res = supabase.table("reports").select("*, ai_predictions(*)").eq("report_status", "Pending HSE Review").order("created_at", desc=True).execute()
    return res.data

class ReviewRequest(BaseModel):
    report_id: str
    reviewer_name: str = "HSE Officer"
    action: str  # Accept, Assign Action, Correct, Close, Reject, Duplicate
    corrections: Optional[dict] = None
    corrective_action: Optional[dict] = None
    comments: str = ""

@app.post("/api/review")
async def submit_review(req: ReviewRequest):
    if not supabase: raise HTTPException(500, "Supabase not connected")
    
    # 1. Map action to status
    status_map = {
        "Accept": "Accepted",
        "Assign Action": "Action Assigned",
        "Action Assigned": "Action Assigned",
        "Correct": "Corrected",
        "Close": "Closed",
        "Reject": "Closed",
        "Duplicate": "Closed"
    }
    new_status = status_map.get(req.action, "Pending HSE Review")
    if req.action == "Accept" and req.corrective_action and req.corrective_action.get("action_plan", "").strip():
        new_status = "Action Assigned"
    
    c = req.corrections or {}

    # 2. Update report status and review_priority on reports table
    report_updates = {"report_status": new_status}
    if c.get("priority"):
        report_updates["review_priority"] = c["priority"]
        
    supabase.table("reports").update(report_updates).eq("report_id", req.report_id).execute()
    
    # 3. Format life saving rules
    rules_val = c.get("life_saving_rules")
    rules_json = json.dumps(rules_val) if isinstance(rules_val, list) else (rules_val if isinstance(rules_val, str) else json.dumps([]))

    # 4. Upsert hse_review entry
    review_data = {
        "report_id": req.report_id,
        "reviewer_name": req.reviewer_name or "HSE Officer",
        "review_status": new_status,
        "hse_comments": req.comments or ("Report closed by HSE Officer" if new_status == "Closed" else ""),
        "final_sif_label": c.get("sif_label", "Non-SIF"),
        "final_priority": c.get("priority", "Medium"),
        "final_activity": c.get("activity", ""),
        "final_hazard": c.get("hazard", ""),
        "final_energy_source": c.get("energy_source", ""),
        "final_exposure": c.get("exposure", ""),
        "final_failed_barrier": c.get("failed_barrier", ""),
        "final_potential_consequence": c.get("precursor_pattern") or c.get("potential_consequence", ""),
        "final_life_saving_rules": rules_json,
        "final_actual_injury": c.get("actual_injury", "")
    }
    supabase.table("hse_reviews").upsert(review_data, on_conflict="report_id").execute()
    
    # 5. Update ai_predictions if corrections provided
    if any(k in c for k in ["hazard", "priority", "sif_label", "precursor_pattern", "life_saving_rules", "summary"]):
        pred_updates = {}
        if c.get("hazard"): pred_updates["hazard"] = c["hazard"]
        if c.get("priority"): pred_updates["priority"] = c["priority"]
        if c.get("sif_label"): pred_updates["sif_label"] = c["sif_label"]
        if c.get("precursor_pattern"): pred_updates["potential_consequence"] = c["precursor_pattern"]
        if rules_json: pred_updates["life_saving_rules"] = rules_json
        if c.get("summary"): pred_updates["explanation"] = c["summary"]
        supabase.table("ai_predictions").update(pred_updates).eq("report_id", req.report_id).execute()

    # 6. Insert Corrective Action if provided
    if req.corrective_action and req.corrective_action.get("action_plan", "").strip():
        ca = req.corrective_action
        supabase.table("corrective_actions").insert({
            "report_id": req.report_id,
            "action_plan": ca.get("action_plan", "").strip(),
            "responsible_department": ca.get("responsible_department", "Safety & HSE"),
            "assigned_to": ca.get("assigned_to", "Unassigned"),
            "priority": ca.get("priority") or c.get("priority", "Medium"),
            "target_date": ca.get("target_date") or datetime.now().strftime("%Y-%m-%d"),
            "status": ca.get("status", "Assigned")
        }).execute()

    return {"success": True, "report_id": req.report_id, "new_status": new_status}

# ==========================================
# ANALYTICS
# ==========================================
@app.get("/api/analytics")
async def get_analytics():
    if not supabase: return {"error": "Database not connected"}
    
    res = supabase.table("reports").select("*, ai_predictions(*), hse_reviews(*)").order("created_at", desc=True).execute()
    reports = res.data or []
    
    total = len(reports)
    critical_count = 0
    closed_count = 0
    sif_count = 0
    
    hazards = {}
    precursors = {}
    risk_levels = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    report_types = {}
    life_saving_rules = {}
    closed_reports = []
    
    for r in reports:
        preds = r.get("ai_predictions")
        ai = preds[0] if isinstance(preds, list) and len(preds) > 0 else (preds if isinstance(preds, dict) else {})
        revs = r.get("hse_reviews")
        rev = revs[0] if isinstance(revs, list) and len(revs) > 0 else (revs if isinstance(revs, dict) else {})
        
        status = r.get("report_status") or "Submitted"
        rev_status = rev.get("review_status") or ""
        is_closed = (status.lower() == "closed") or (rev_status.lower() == "closed")
        
        if is_closed:
            closed_count += 1
            closed_reports.append({
                "id": r.get("id"),
                "report_id": r.get("report_id"),
                "report_type": r.get("report_type", "Report"),
                "report_summary": ai.get("explanation") or r.get("report_summary") or rev.get("hse_comments") or r.get("original_text") or "Closed report",
                "original_text": r.get("original_text"),
                "review_priority": (rev.get("final_priority") if rev.get("final_priority") and rev.get("final_priority") != "Unknown" else None) or r.get("review_priority") or ai.get("priority") or "Low",
                "report_status": "Closed",
                "reviewer_name": rev.get("reviewer_name") or "HSE Officer",
                "hse_comments": rev.get("hse_comments") or "",
                "created_at": r.get("created_at"),
                "reviewed_at": rev.get("reviewed_at") or r.get("created_at")
            })
            
        priority = (rev.get("final_priority") if rev.get("final_priority") and rev.get("final_priority") != "Unknown" else None) or r.get("review_priority") or ai.get("priority") or "Low"
        if priority in ["Critical", "High"]:
            critical_count += 1
        if priority in risk_levels:
            risk_levels[priority] += 1
        else:
            risk_levels["Low"] += 1
            
        sif_label = (rev.get("final_sif_label") if rev.get("final_sif_label") and rev.get("final_sif_label") != "Unknown" else None) or ai.get("sif_label")
        if sif_label == "SIF-potential":
            sif_count += 1
            
        rtype = r.get("report_type", "Manual/CSV Input")
        report_types[rtype] = report_types.get(rtype, 0) + 1
        
        h = rev.get("final_hazard") or ai.get("hazard")
        if h and h not in ["Not identified", "None", "Hazard not identified"]:
            hazards[h] = hazards.get(h, 0) + 1
            
        p = rev.get("final_potential_consequence") or ai.get("potential_consequence") or ai.get("precursor_pattern")
        if p and p not in ["Not identified", "None"]:
            precursors[p] = precursors.get(p, 0) + 1
            
        raw_rules = rev.get("final_life_saving_rules") or ai.get("life_saving_rules")
        if raw_rules:
            rules_list = []
            if isinstance(raw_rules, list):
                rules_list = raw_rules
            elif isinstance(raw_rules, str) and raw_rules.strip():
                try:
                    parsed = json.loads(raw_rules)
                    if isinstance(parsed, list):
                        rules_list = parsed
                    elif isinstance(parsed, str):
                        rules_list = [parsed]
                except Exception:
                    rules_list = [raw_rules.strip()]
            for rule in rules_list:
                rule_str = str(rule).strip()
                if rule_str and rule_str not in ["No applicable rule", "[]", "None", "null"]:
                    life_saving_rules[rule_str] = life_saving_rules.get(rule_str, 0) + 1
                    
    top_precursor = "None"
    top_precursor_count = 0
    for k, v in precursors.items():
        if v > top_precursor_count:
            top_precursor = k
            top_precursor_count = v
            
    sif_percentage = round((sif_count / total * 100) if total > 0 else 0, 1)
    
    return {
        "total_reports": total,
        "sif_count": sif_count,
        "critical_count": critical_count,
        "closed_count": closed_count,
        "sif_percentage": sif_percentage,
        "hazards": hazards,
        "precursors": precursors,
        "riskLevels": risk_levels,
        "reportTypes": report_types,
        "lifeSavingRules": life_saving_rules,
        "topPrecursor": top_precursor,
        "topPrecursorCount": top_precursor_count,
        "closed_reports": closed_reports
    }
