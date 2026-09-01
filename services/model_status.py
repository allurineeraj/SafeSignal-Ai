from services.stt import is_whisper_available
from services.translation import is_translation_available

def get_model_statuses() -> dict:
    """Returns dynamic status checks for AI models."""
    
    whisper_active = is_whisper_available()
    translation_active = is_translation_available()
    
    return {
        "Rule Engine": {
            "status": True,
            "label": "Rule-based Safety Engine Active"
        },
        "ML Classifier": {
            "status": False,
            "label": "Rule-engine fallback mode"
        },
        "Whisper STT": {
            "status": whisper_active,
            "label": "ACTIVE - LOCAL" if whisper_active else "UNAVAILABLE / FALLBACK"
        },
        "Translation": {
            "status": translation_active,
            "label": "ACTIVE - LOCAL" if translation_active else "UNAVAILABLE / FALLBACK"
        },
        "Similarity Model": {
            "status": False,
            "label": "TF-IDF Cosine Similarity active"
        },
        "OCR Engine": {
            "status": False,
            "label": "OCR disabled (Tesseract binary missing)"
        }
    }
