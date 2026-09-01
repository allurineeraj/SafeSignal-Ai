import os
import streamlit as st
import numpy as np

try:
    import whisper
    import torch
    import scipy.io.wavfile as wav
    import scipy.signal as signal
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

def is_whisper_available() -> bool:
    """Checks if local Whisper is available and loadable for STT."""
    if not HAS_WHISPER:
        return False
    # Check if the model can be loaded by testing the cache or attempting to load it
    try:
        get_whisper_model()
        return True
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def get_whisper_model():
    """Lazily loads and caches the Whisper model."""
    if not HAS_WHISPER:
        raise ImportError("Whisper dependencies not installed.")
        
    model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Whisper model '{model_size}' on {device}...")
    model = whisper.load_model(model_size, device=device)
    return model

def load_audio_without_ffmpeg(file_path: str) -> np.ndarray:
    """Reads a WAV file, converts to mono, resamples to 16kHz for Whisper without FFmpeg."""
    try:
        import soundfile as sf
        data, rate = sf.read(file_path)
    except Exception as e:
        # Fallback to scipy if soundfile fails
        print(f"Soundfile read failed: {e}. Falling back to scipy.")
        rate, data = wav.read(file_path)
        # Normalize to float32 if int16
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
            
    if data.ndim > 1:
        data = data.mean(axis=1) # mix to mono
        
    data = data.astype(np.float32)
    
    if rate != 16000:
        num_samples = int(len(data) * 16000 / rate)
        data = signal.resample(data, num_samples).astype(np.float32)
        
    return data

def transcribe_audio(file_path: str, language: str = "English") -> tuple[str, str]:
    """Transcribes audio using local Whisper or returns fallback mode."""
    if not HAS_WHISPER:
        return "[Demo/Fallback Mode] Speech recognition dependencies missing. Please type your report manually.", "Fallback"

    try:
        model = get_whisper_model()
        
        # Determine language code for Whisper
        # Whisper uses iso-639-1 language codes (e.g. 'en', 'hi', 'te', 'as')
        lang_map = {
            "English": "en",
            "Hindi": "hi",
            "Telugu": "te",
            "Assamese": "as" 
        }
        lang_code = lang_map.get(language, "en")
        
        # Load and process audio without FFmpeg
        audio_array = load_audio_without_ffmpeg(file_path)
        
        # Transcribe
        result = model.transcribe(audio_array, language=lang_code, fp16=torch.cuda.is_available())
        
        result_text = result["text"].strip() if result["text"] else "[Error] Empty response from Whisper STT."
        return result_text, "Local Whisper"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[Demo/Fallback Mode] Local STT failed: {str(e)}. Please type manually.", "Error"
