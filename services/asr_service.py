import os
import re
import numpy as np
from dotenv import load_dotenv

load_dotenv()

_model = None

MODEL_SIZE = os.getenv("ASR_MODEL_SIZE", "medium")
SAMPLE_RATE = 16000


def _load_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"[ASR] Loading faster-whisper '{MODEL_SIZE}' on CPU with INT8...")
        _model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type="int8",        #  INT8 quantization for CPU speedup
        )
        print("[ASR] Model ready.")
    return _model


def get_pipeline():
    return _load_model()


def clean_audio(file_path: str) -> np.ndarray:
    """Load and validate audio file."""
    try:
        import librosa
        print(f"[Audio] Loading: {file_path}")
        audio, sr = librosa.load(file_path, sr=SAMPLE_RATE, mono=True)
        duration = len(audio) / SAMPLE_RATE
        print(f"[Audio] Loaded: {duration:.1f}s, {len(audio)} samples")
        return audio
    except Exception as e:
        print(f"[Audio] Load error: {e}")
        return None


def _clean_text(text: str) -> str:
    """Remove special Whisper tokens and extra whitespace."""
    # Remove any <|token|> style special tokens
    text = re.sub(r'<\|[^|]+\|>', '', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def transcribe_audio(file_path: str, initial_prompt: str = None) -> str:
    model = _load_model()

    # Quick audio validation
    audio = clean_audio(file_path)
    if audio is None or len(audio) == 0:
        print("[ASR] ERROR: Could not load audio.")
        return ""

    duration = len(audio) / SAMPLE_RATE
    print(f"[ASR] Transcribing {duration:.1f}s of audio...")

    try:
        # ✅ faster-whisper handles chunking internally — no manual loop needed
        segments, info = model.transcribe(
            file_path,
            language="ar",
            task="transcribe",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=True,
            vad_filter=False,
            word_timestamps=False,
        )

        print(f"[ASR] Detected language: {info.language} "
              f"(probability: {info.language_probability:.2f})")

        # ✅ Collect all segments (generator — must iterate)
        results = []
        for segment in segments:
            text = _clean_text(segment.text)
            if text:
                print(f"[ASR] Segment [{segment.start:.1f}s → {segment.end:.1f}s]: "
                      f"'{text}'")
                results.append(text)

        full_text = " ".join(results)
        print(f"[ASR] Done. Total: {len(full_text)} chars across {len(results)} segments.")

        if not full_text:
            print("[ASR] WARNING: Empty transcription!")

        return full_text

    except Exception as e:
        print(f"[ASR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ""