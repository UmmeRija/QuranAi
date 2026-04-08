"""
Whisper Service
---------------
Whisper model ko sirf ek baar load karta hai (singleton pattern).
Har API request par dobara load hone se bachata hai — performance ke liye zaroori.
"""

import whisper
import os
from dotenv import load_dotenv

load_dotenv()

_model = None  # Global singleton


def get_model() -> whisper.Whisper:
    """Whisper model load karo (sirf pehli baar)."""
    global _model
    if _model is None:
        model_size = os.getenv("WHISPER_MODEL", "base")
        print(f"[Whisper] Loading '{model_size}' model — please wait...")
        _model = whisper.load_model(model_size)
        print(f"[Whisper] '{model_size}' model loaded successfully!")
    return _model


def transcribe_audio(file_path: str) -> str:
    """
    Audio file ko Arabic text mein badlo.
    
    Args:
        file_path: Temporary audio file ka path
        
    Returns:
        Transcribed Arabic text (string)
    """
    model = get_model()
    result = model.transcribe(
        file_path,
        language="ar",           # Arabic force karo
        task="transcribe",
        fp16=False,               # CPU-safe mode
        temperature=0,            # Deterministic output
    )
    return result["text"].strip()
