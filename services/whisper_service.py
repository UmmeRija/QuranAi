"""
Whisper Service — DEPRECATED WRAPPER
-------------------------------------
Yeh file ab sirf backward compatibility ke liye hai.
Asli kaam asr_service.py karta hai jo Tarteel Quran-specialized model use karta hai.

Agar koi purana code is file ko import karta hai, woh automatically
asr_service.py pe redirect ho jata hai.
"""

from asr_service import transcribe_audio, clean_audio, get_pipeline

# Legacy alias — purana code jo whisper_service.transcribe_audio call karta tha
# ab automatically Tarteel model use karega
__all__ = ["transcribe_audio", "clean_audio", "get_pipeline"]

print("[WhisperService] WARNING: whisper_service.py deprecated. Using asr_service.py (Tarteel model).")