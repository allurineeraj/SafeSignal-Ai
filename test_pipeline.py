import sys
import os
import streamlit as st

# Setup mock st.session_state for testing
class MockSessionState(dict):
    def __getattr__(self, name):
        return self.get(name, None)
    def __setattr__(self, name, value):
        self[name] = value
        
st.session_state = MockSessionState()
st.session_state.processed_audio_hashes = set()
st.session_state.voice_processed = False

from services.stt import transcribe_audio, is_whisper_available
from services.translation import translate_to_english, is_translation_available
from services.classifier import classify_report
from database.db import save_report, save_ai_prediction, update_report_status
from services.model_status import get_model_statuses

def run_test(audio_file, lang):
    print(f"\n--- Testing {lang.upper()} Pipeline ---")
    print(f"1. Transcribing {audio_file}...")
    stt_text, stt_status = transcribe_audio(audio_file, language=lang)
    print(f"STT Output ({stt_status}): {stt_text}")
    
    if stt_status in ["Error", "Fallback"]:
        print("STT FAILED. Aborting.")
        return False
        
    print(f"2. Translating...")
    if lang != "English":
        translated, tr_status = translate_to_english(stt_text, lang)
    else:
        translated, tr_status = stt_text, "Original English"
        
    print(f"Translation Output ({tr_status}): {translated}")
    
    if tr_status in ["Error", "Fallback/Demo"]:
        print("TRANSLATION FAILED. Aborting.")
        return False
        
    print("3. Classifying Report...")
    classifier_results = classify_report(translated, immediate_action="", immediate_danger=False)
    print(f"Classification Priority: {classifier_results['priority']}")
    print(f"Classification Label: {classifier_results['sif_label']}")
    print(f"Explanation: {classifier_results['explanation'][:100]}...")
    
    print("4. Saving to DB...")
    report_data = {
        "report_type": "Incident",
        "site": "Test Site",
        "location": "Test Location",
        "original_text": stt_text,
        "original_language": lang,
        "translated_text": translated,
        "immediate_action": "",
        "anonymous": 1,
        "submitted_on_behalf": 0,
        "submitted_by": "TestBot",
        "source_type": "automated_test",
        "immediate_danger": 0,
        "review_priority": classifier_results["priority"],
        "report_status": "Submitted",
        "audio_path": audio_file
    }
    report_id = save_report(report_data)
    
    ai_data = {
        "report_id": report_id,
        "sif_label": classifier_results["sif_label"],
        "sif_score": classifier_results["sif_score"],
        "priority": classifier_results["priority"],
        "activity": classifier_results["activity"],
        "hazard": classifier_results["hazards"],
        "energy_source": classifier_results["energy_sources"],
        "exposure": classifier_results["exposure"],
        "failed_barrier": ", ".join(classifier_results["failed_barriers"]) if isinstance(classifier_results["failed_barriers"], list) else classifier_results["failed_barriers"],
        "potential_consequence": classifier_results["potential_consequences"],
        "life_saving_rules": classifier_results["life_saving_rules"],
        "evidence_phrases": classifier_results["evidence_phrases"],
        "actual_injury": classifier_results["actual_injury"],
        "explanation": classifier_results["explanation"],
        "llm_provider": classifier_results["llm_provider"],
        "llm_model": classifier_results["llm_model"],
        "llm_analysis_status": classifier_results["llm_analysis_status"],
        "llm_confidence": classifier_results["llm_confidence"],
        "classifier_mode": classifier_results["classifier_mode"],
        "model_version": classifier_results["model_version"]
    }
    save_ai_prediction(ai_data)
    update_report_status(report_id, "Pending HSE Review", "System", "System")
    print(f"SUCCESS: Report #{report_id} saved and queued for HSE Review.")
    return True

def main():
    print("Checking Models...")
    print(f"Whisper Available: {is_whisper_available()}")
    print(f"Translation Available: {is_translation_available()}")
    print("Model Statuses:", get_model_statuses())
    
    tests = [
        ("test_audio/telugu_test.mp3", "Telugu"),
        ("test_audio/hindi_test.mp3", "Hindi"),
        ("test_audio/assamese_test.mp3", "Assamese"),
        ("test_audio/english_test.mp3", "English")
    ]
    
    success = True
    for audio_file, lang in tests:
        if os.path.exists(audio_file):
            if not run_test(audio_file, lang):
                success = False
        else:
            print(f"Missing file {audio_file}")
            
    if success:
        print("\nALL PIPELINE TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED.")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
