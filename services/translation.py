import os
import streamlit as st

try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    HAS_TRANSLATORS = True
except ImportError:
    HAS_TRANSLATORS = False

SUPPORTED_LANGUAGES = {
    "English": "eng_Latn",
    "Hindi": "hin_Deva",
    "Telugu": "tel_Telu",
    "Assamese": "asm_Beng"
}

def is_translation_available() -> bool:
    """Checks if local translation models are available and loadable."""
    if not HAS_TRANSLATORS:
        return False
    try:
        get_translation_model()
        return True
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def get_translation_model():
    """Lazily loads the IndicTrans2 model and tokenizer."""
    if not HAS_TRANSLATORS:
        raise ImportError("Transformers or Torch not installed.")
    
    model_name = os.environ.get("INDICTRANS_MODEL", "ai4bharat/indictrans2-indic-en-1B")
    print(f"Loading translation model '{model_name}'...")
    
    # trust_remote_code is required for IndicTrans2
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
    
    if torch.cuda.is_available():
        model = model.cuda()
    
    model.eval()
    return tokenizer, model

def translate_to_english(text: str, source_lang: str) -> tuple[str, str]:
    """Translates text to English using local IndicTrans2 or returns fallback."""
    if source_lang == "English":
        return text, "Original English"
        
    if not HAS_TRANSLATORS:
        return f"[Demo/Fallback Mode] Local translation dependencies missing. Original text: {text}", "Fallback/Demo"

    try:
        tokenizer, model = get_translation_model()
        
        # Format the input. According to the AI4Bharat IndicTrans2 repo, for inference:
        # encoded = tokenizer(text, src=src_lang, return_tensors="pt")
        # But we will use the standard tokenizer API which works for the HF pipeline
        encoded = tokenizer(text, return_tensors="pt")
        
        if torch.cuda.is_available():
            encoded = {k: v.cuda() for k, v in encoded.items()}
            
        generated_tokens = model.generate(
            **encoded,
            use_cache=True,
            min_length=0,
            max_length=256,
            num_beams=4
        )
        
        # Decode
        decoded_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        
        return decoded_text, "Local IndicTrans2"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[Demo/Fallback Mode] Local translation failed ({str(e)}). Original: {text}", "Fallback/Demo"
