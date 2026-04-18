"""
Whisper Service
---------------
Whisper model ko sirf ek baar load karta hai (singleton pattern).
Har API request par dobara load hone se bachata hai — performance ke liye zaroori.
"""

import whisper
import os
import io
import numpy as np
from pydub import AudioSegment
import noisereduce as nr
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


def clean_audio(file_path: str) -> str:
    """
    Audio file se background noise aur echo kam karne ke liye.
    Returns: cleaned temp file path
    """
    try:
        print(f"[Audio] Cleaning: {file_path}")
        # 1. Load audio
        audio = AudioSegment.from_file(file_path)
        
        # 2. Convert to numpy array
        # Note: Whisper prefers 16kHz mono
        audio = audio.set_frame_rate(16000).set_channels(1)
        samples = np.array(audio.get_array_of_samples())
        
        # 3. Reduce noise (stationary noise removal)
        # Lower prop_decrease (0.60) to avoid removing actual voice signal
        reduced_noise = nr.reduce_noise(y=samples, sr=audio.frame_rate, prop_decrease=0.60)
        
        # 4. Convert back to AudioSegment
        cleaned_audio = audio._spawn(reduced_noise.astype(np.int16))
        
        # 5. Apply minimal filters to keep the voice natural
        cleaned_audio = cleaned_audio.high_pass_filter(80) # Remove only very low rumble
        
        # 6. Normalize to ensure consistent volume without clipping
        cleaned_audio = cleaned_audio.normalize()
        
        # 7. Save to temp file
        base, ext = os.path.splitext(file_path)
        cleaned_file_path = f"{base}_cleaned.wav"
        cleaned_audio.export(cleaned_file_path, format="wav")
        
        return cleaned_file_path
    except Exception as e:
        print(f"[Audio] Cleaning error: {e}")
        return file_path  # Fallback to original if cleaning fails


def transcribe_audio(file_path: str, initial_prompt: str = None) -> str:
    """
    Audio file ko Arabic text mein badlo.
    
    Args:
        file_path: Temporary audio file ka path
        initial_prompt: Context (correct text) to guide Whisper
        
    Returns:
        Transcribed Arabic text (string)
    """
    # Audio clean karo agar shor ho
    cleaned_path = clean_audio(file_path)
    
    model = get_model()
    result = model.transcribe(
        cleaned_path,
        language="ar",           # Arabic force karo
        task="transcribe",
        fp16=False,               # CPU-safe mode
        temperature=0.5,          # High creativity for regional accents
        initial_prompt=initial_prompt, # Context guide
        no_speech_threshold=0.4,  # Lower threshold for quiet/normal people
    )
    
    # Cleaned file delete karo kaam khatam hone par
    if cleaned_path != file_path and os.path.exists(cleaned_path):
        os.remove(cleaned_path)
        
    return result["text"].strip()
