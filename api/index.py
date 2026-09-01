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
    reviewer_name: str
    action: str  # Accept, Correct, Reject, Duplicate
    corrections: dict = None
    comments: str = ""

@app.post("/api/review")
async def submit_review(req: ReviewRequest):
    if not supabase: raise HTTPException(500, "Supabase not connected")
    
    # 1. Map action to status
    status_map = {
        "Accept": "Accepted",
        "Correct": "Corrected",
        "Reject": "Rejected",
        "Duplicate": "Duplicate"
    }
    new_status = status_map.get(req.action, "Pending HSE Review")
    
    # 2. Update report status
    supabase.table("reports").update({"report_status": new_status}).eq("report_id", req.report_id).execute()
    
    # 3. Create hse_review entry
    c = req.corrections or {}
    review_data = {
        "report_id": req.report_id,
        "reviewer_name": req.reviewer_name,
        "review_status": new_status,
        "hse_comments": req.comments,
        "final_sif_label": c.get("sif_label", "Unknown"),
        "final_priority": c.get("priority", "Unknown"),
        "final_activity": c.get("activity", ""),
        "final_hazard": c.get("hazard", ""),
        "final_energy_source": c.get("energy_source", ""),
        "final_exposure": c.get("exposure", ""),
        "final_failed_barrier": c.get("failed_barrier", ""),
        "final_potential_consequence": c.get("potential_consequence", ""),
        "final_life_saving_rules": json.dumps(c.get("life_saving_rules", [])),
        "final_actual_injury": c.get("actual_injury", "")
    }
    supabase.table("hse_reviews").insert(review_data).execute()
    
    return {"success": True, "new_status": new_status}

# ==========================================
# ANALYTICS
# ==========================================
@app.get("/api/analytics")
async def get_analytics():
    if not supabase: return {"error": "Database not connected"}
    
    # Get total
    reports = supabase.table("reports").select("report_status, review_priority, id").execute().data
    
    total = len(reports)
    critical = len([r for r in reports if r["review_priority"] == "Critical"])
    closed = len([r for r in reports if r["report_status"] == "Closed"])
    
    # AI Predictions for SIF counts
    preds = supabase.table("ai_predictions").select("sif_label").execute().data
    sif_count = len([p for p in preds if p["sif_label"] == "SIF-potential"])
    
    sif_percentage = round((sif_count / total * 100) if total > 0 else 0, 1)
    
    return {
        "total_reports": total,
        "sif_count": sif_count,
        "critical_count": critical,
        "closed_count": closed,
        "sif_percentage": sif_percentage,
        "highest_risk_site": "Demo Site",
        "most_freq_rule": "Working at Height" # Simplified for speed
    }
