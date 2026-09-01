import streamlit as st
import os
import uuid
from services.classifier import classify_report
from database.db import save_report, save_ai_prediction, update_report_status
from services.text_extraction import extract_text_from_file
from services.similar_search import check_for_duplicates
from services.stt import transcribe_audio
from services.translation import translate_to_english, SUPPORTED_LANGUAGES

# Uploads directory setup
UPLOADS_DIR = "uploads"
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

st.set_page_config(page_title="Worker Report Submission", page_icon="📝", layout="wide")

# Sync Role Selector from Session State
st.sidebar.markdown("### 🛠️ DEMO CONTROLS")
if "user_role" not in st.session_state:
    st.session_state.user_role = "Worker / Observer"

user_role = st.sidebar.selectbox(
    "Active User Role (Demo Mode)",
    ["Worker / Observer", "Supervisor", "HSE Officer", "HSE Manager", "Administrator"],
    index=["Worker / Observer", "Supervisor", "HSE Officer", "HSE Manager", "Administrator"].index(st.session_state.user_role)
)
st.session_state.user_role = user_role

st.title("📝 Worker Safety Report Submission")
st.subheader("Submit unsafe acts, unsafe conditions, near misses, or incidents to the HSE division.")

# 1. Immediate Danger Check (Prominent at top)
st.markdown("### 🚨 Current Hazard Severity Check")
immediate_danger_input = st.radio(
    "Is anyone currently in immediate danger?",
    ["NO", "YES"],
    index=0,
    help="Select YES if there is an active threat to life, health, or critical asset integrity."
)

is_danger = False
if immediate_danger_input == "YES":
    is_danger = True
    st.error(
        "🔥 **EMERGENCY SAFETY PROTOCOL INITIATED**\n\n"
        "1. Stop work immediately and move to a safe muster point.\n"
        "2. Isolate/shut down equipment if safe to do so.\n"
        "3. Call OIL Emergency Hotline / Control Room immediately.\n"
        "4. Inform your area supervisor.\n\n"
        "*SIF-Insight processing is a classification utility and does NOT initiate emergency services or on-site rescue.*"
    )

st.markdown("---")

# 2. Main Form Fields
st.markdown("### 📋 Safety Report Information")
col1, col2 = st.columns(2)

with col1:
    report_type = st.selectbox(
        "Report Type *",
        ["Unsafe Act", "Unsafe Condition", "Near Miss", "Incident"]
    )
    
    site = st.selectbox(
        "Site / Facility *",
        ["Duliajan HQ", "Digboi Oilfield", "Moran Field", "Jorhat Office", "Guwahati Pipeline", "Kolkata Hub", "Other"]
    )
    if site == "Other":
        site = st.text_input("Specify Facility Name *")
        
    location = st.text_input(
        "Exact Location / Well Number / Plant Area *",
        placeholder="e.g. Drilling Rig 4, Compressor Station A"
    )

with col2:
    is_anonymous = st.checkbox("Submit anonymously")
    
    # Check permissions for on-behalf reporting
    can_on_behalf = st.session_state.user_role in ["Supervisor", "HSE Officer", "HSE Manager", "Administrator"]
    
    if can_on_behalf:
        is_on_behalf = st.checkbox("Submit on behalf of another worker")
        reporter_name = st.text_input("Reporter Name / ID *", value="", placeholder="Enter employee name or ID") if not is_anonymous else "Anonymous"
    else:
        is_on_behalf = False
        st.info("💡 *On-behalf reporting is restricted to Supervisors and HSE Officers. (Change role in sidebar to unlock).*")
        reporter_name = "Anonymous" if is_anonymous else st.text_input("Reporter Name / ID *", value="", placeholder="Enter your employee ID")

st.markdown("---")
st.markdown("### 🎤 Voice Report Submission")
st.info("Speak in your preferred language. The system will convert your speech into a safety report.")

voice_lang = st.selectbox("Select Language for Voice Recording", list(SUPPORTED_LANGUAGES.keys()), index=0)

audio_value = st.audio_input("Record your safety report")

# Voice Processing State
if "voice_processed" not in st.session_state:
    st.session_state.voice_processed = False
if "voice_text" not in st.session_state:
    st.session_state.voice_text = ""
if "translated_text" not in st.session_state:
    st.session_state.translated_text = ""
if "voice_audio_path" not in st.session_state:
    st.session_state.voice_audio_path = None
if "voice_lang" not in st.session_state:
    st.session_state.voice_lang = "English"
if "processed_audio_hashes" not in st.session_state:
    st.session_state.processed_audio_hashes = set()
if "auto_submit_trigger" not in st.session_state:
    st.session_state.auto_submit_trigger = False

if audio_value:
    import hashlib
    audio_bytes = audio_value.read()
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    
    if audio_hash not in st.session_state.processed_audio_hashes and not st.session_state.voice_processed:
        with st.spinner("Processing audio with Local AI..."):
            # Save audio file
            filename = f"voice_{uuid.uuid4().hex[:8]}.wav"
            save_path = os.path.join(UPLOADS_DIR, filename)
            with open(save_path, "wb") as f:
                f.write(audio_bytes)
                
            st.session_state.voice_audio_path = save_path
            st.session_state.voice_lang = voice_lang
            
            # Transcribe
            stt_text, stt_status = transcribe_audio(save_path, language=voice_lang)
            st.session_state.voice_text = stt_text if stt_text else "[Error] No transcription returned."
            
            if stt_status in ["Fallback", "Error"]:
                st.error(f"Voice Processing Halted: {st.session_state.voice_text}")
                st.session_state.voice_processed = False
            else:
                # Translate if necessary
                if voice_lang != "English":
                    translated, tr_status = translate_to_english(st.session_state.voice_text, voice_lang)
                    st.session_state.translated_text = translated if translated else "[Error] No translation returned."
                    if tr_status in ["Fallback/Demo", "Error"]:
                        st.error(f"Translation Halted: {st.session_state.translated_text}")
                        st.session_state.voice_processed = False
                    else:
                        st.session_state.voice_processed = True
                else:
                    st.session_state.translated_text = st.session_state.voice_text
                    st.session_state.voice_processed = True
                    
            if st.session_state.voice_processed:
                st.session_state.processed_audio_hashes.add(audio_hash)
                st.session_state.auto_submit_trigger = True
                st.rerun()

if st.session_state.voice_processed:
    st.success("Audio processed!")
    st.markdown(f"**Original Speech ({st.session_state.voice_lang}):** {st.session_state.voice_text}")
    if st.session_state.voice_lang != "English":
        st.markdown(f"**Translated (English):** {st.session_state.translated_text}")
        
    if st.button("Clear Recording"):
        st.session_state.voice_processed = False
        st.session_state.voice_text = ""
        st.session_state.translated_text = ""
        st.session_state.voice_audio_path = None
        st.rerun()

st.markdown("#### Safety Narrative & Description")
default_desc = st.session_state.translated_text if st.session_state.voice_processed else ""
description = st.text_area(
    "Describe the unsafe act, condition, near miss, or incident *",
    value=default_desc,
    placeholder="Describe exactly what happened. What hazards were present? Did any equipment fail? Were life-saving rules violated? (English, Hindi, or Mixed)",
    height=150
)

immediate_action = st.text_area(
    "Immediate Action Taken / Barriers Applied",
    placeholder="What did you or others do immediately to control the hazard or prevent injury?",
    height=80
)

# 3. File Attachments
st.markdown("### 📎 File Attachments & Media")
uploaded_file = st.file_uploader(
    "Attach media or documents (Audio, PDF, Word, TXT, Excel, Image)",
    type=["wav", "mp3", "pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"]
)

attachment_path = None
attachment_type = None

if uploaded_file:
    # Size check (10MB limit)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    uploaded_file.seek(0, os.SEEK_END)
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        st.error(f"❌ File size exceeds 10MB limit ({file_size / (1024*1024):.2f}MB). Please upload a smaller file.")
    else:
        # Secure filename and save
        safe_filename = "".join([c if c.isalnum() or c in (".", "-", "_") else "_" for c in uploaded_file.name])
        # Add random prefix to avoid duplicates
        filename = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
        save_path = os.path.join(UPLOADS_DIR, filename)
        
        with open(save_path, "wb") as f:
            f.write(uploaded_file.read())
            
        attachment_path = save_path
        attachment_type = uploaded_file.type
        st.success(f"✓ Attachment '{uploaded_file.name}' uploaded successfully.")
        
        # Extract text from attachment if possible
        with st.spinner("Extracting text from attachment..."):
            extracted_text = extract_text_from_file(attachment_path)
            if extracted_text and not extracted_text.startswith("["):
                # We have actual extracted text, append it to description
                st.info("📄 Text extracted from attachment and added to narrative.")
                description = f"{description}\n\n--- Attachment Extracted Text ---\n{extracted_text}"
            elif extracted_text.startswith("["):
                st.warning(f"ℹ️ {extracted_text}")

# 4. Form Submission Action
st.markdown("---")
auto_submit = st.session_state.get("auto_submit_trigger", False)
manual_submit = st.button("Submit Safety Report", type="primary")

if auto_submit or manual_submit:
    st.session_state.auto_submit_trigger = False # reset trigger
    # Input validation
    errors = []
    if not description.strip():
        errors.append("Description is required.")
        
    if not auto_submit:
        if not location.strip():
            errors.append("Location is required.")
        if not site:
            errors.append("Site / Facility is required.")
        if not is_anonymous and not reporter_name.strip():
            errors.append("Reporter Name / ID is required when not anonymous.")
    else:
        # Default fields for voice-first report if they weren't filled out
        location = location.strip() if location.strip() else "Voice Report Location"
        site = site if site else "Other"
        
    if errors:
        for err in errors:
            st.error(err)
    else:
        # Check for duplicates before processing
        is_duplicate, similar_reports = check_for_duplicates(description)
        if is_duplicate:
            st.warning("⚠️ Similar report(s) detected in the system. Submitting anyway.")
            with st.expander("View Similar Reports"):
                for sim in similar_reports:
                    st.markdown(f"- **ID #{sim['id']}** ({sim['report_type']}): Similarity Score {sim['similarity_score'] * 100:.1f}%")

        with st.spinner("Processing safety report..."):
            try:
                # 1. Run classifier on narrative first to extract details and priority
                classifier_results = classify_report(description, immediate_action=immediate_action, immediate_danger=is_danger)
                
                # 2. Compile reports database columns
                report_data = {
                    "report_type": report_type,
                    "site": site,
                    "location": location,
                    "original_text": st.session_state.voice_text if st.session_state.voice_processed else description,
                    "original_language": st.session_state.voice_lang if st.session_state.voice_processed else "English",
                    "translated_text": description if st.session_state.voice_processed else None,
                    "immediate_action": immediate_action,
                    "anonymous": 1 if is_anonymous else 0,
                    "submitted_on_behalf": 1 if is_on_behalf else 0,
                    "submitted_by": "Anonymous" if is_anonymous else reporter_name,
                    "source_type": "web_form",
                    "immediate_danger": 1 if is_danger else 0,
                    "review_priority": classifier_results["priority"],
                    "report_status": "Submitted"
                }
                
                # Attachment type and paths
                if st.session_state.voice_processed and st.session_state.voice_audio_path:
                    report_data["audio_path"] = st.session_state.voice_audio_path
                elif attachment_path:
                    ext = attachment_path.split(".")[-1].lower()
                    if ext in ["wav", "mp3"]:
                        report_data["audio_path"] = attachment_path
                    elif ext in ["png", "jpg", "jpeg"]:
                        report_data["image_path"] = attachment_path
                    else:
                        report_data["document_path"] = attachment_path
                
                # 3. Persist raw report to database
                report_id = save_report(report_data)
                
                # 4. Map classifier result keys to ai_predictions columns
                ai_data = {
                    "report_id": report_id,
                    "sif_label": classifier_results["sif_label"],
                    "sif_score": classifier_results["sif_score"],
                    "confidence": classifier_results.get("ml_confidence"),
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
                
                # 5. Persist AI prediction
                save_ai_prediction(ai_data)
                
                # 6. Move status to Pending HSE Review
                update_report_status(report_id, "Pending HSE Review", "System", "System")
                
                st.balloons()
                
                # 7. Render Confirmation
                st.success("🎉 Safety Report Submitted Successfully!")
                st.markdown("### 📝 Submission Confirmation")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Report ID", f"#{report_id}")
                    st.metric("Status", "Pending HSE Review")
                with c2:
                    st.metric("SIF Assessment", classifier_results["sif_label"])
                    st.metric("Review Priority", classifier_results["priority"])
                with c3:
                    st.metric("Immediate Danger", "YES" if is_danger else "NO")
                    st.metric("Matched Rules Count", len(classifier_results["life_saving_rules"]))
                    
                st.info(f"**Life-Saving Rules Triggered**: {', '.join(classifier_results['life_saving_rules']) if classifier_results['life_saving_rules'] else 'None'}")
                
                st.markdown("#### Quick Summary")
                st.code(classifier_results["explanation"], language="markdown")
                
                # Clear voice state after successful submission
                st.session_state.voice_processed = False
                st.session_state.voice_text = ""
                st.session_state.translated_text = ""
                st.session_state.voice_audio_path = None
                
            except Exception as e:
                st.error(f"❌ Database error: {str(e)}")
