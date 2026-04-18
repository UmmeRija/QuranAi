"""
Audio Reference Service
-----------------------
EveryAyah.com se reference audio download karta hai (on-demand + cache).
MFCC features extract karta hai aur DTW se pronunciation similarity score
calculate karta hai.

Reference Qari: Mishary Rashid Alafasy (128kbps) — default
URL Pattern: https://everyayah.com/data/{reciter}/{surah:03d}{ayah:03d}.mp3
"""

import os
import requests
import numpy as np
import librosa
from fastdtw import fastdtw
from scipy.spatial.distance import cosine as cosine_distance
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
DEFAULT_RECITER = os.getenv("REFERENCE_RECITER", "Alafasy_128kbps")
EVERYAYAH_BASE_URL = "https://everyayah.com/data"
REFERENCE_AUDIO_DIR = os.path.join("data", "reference_audio")

# MFCC extraction parameters
N_MFCC = 13       # Number of MFCC coefficients
HOP_LENGTH = 512   # Hop length for MFCC
N_FFT = 2048       # FFT window size


def _get_audio_url(surah: int, ayah: int, reciter: str = None) -> str:
    """EveryAyah URL construct karo."""
    reciter = reciter or DEFAULT_RECITER
    filename = f"{surah:03d}{ayah:03d}.mp3"
    return f"{EVERYAYAH_BASE_URL}/{reciter}/{filename}"


def _get_cache_path(surah: int, ayah: int, reciter: str = None) -> str:
    """Local cache path return karo."""
    reciter = reciter or DEFAULT_RECITER
    reciter_dir = os.path.join(REFERENCE_AUDIO_DIR, reciter)
    os.makedirs(reciter_dir, exist_ok=True)
    return os.path.join(reciter_dir, f"{surah:03d}{ayah:03d}.mp3")


def download_reference_audio(surah: int, ayah: int, reciter: str = None) -> str:
    """
    Reference audio download karo (ya cache se laao).

    Args:
        surah: Surah number (1-114)
        ayah: Ayah number
        reciter: Reciter folder name (default: Alafasy_128kbps)

    Returns:
        Local file path to the reference audio
    """
    cache_path = _get_cache_path(surah, ayah, reciter)

    # Cache check
    if os.path.exists(cache_path):
        return cache_path

    # Download
    url = _get_audio_url(surah, ayah, reciter)
    print(f"[RefAudio] Downloading: {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=15, stream=True)
        resp.raise_for_status()

        with open(cache_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[RefAudio] Saved: {cache_path}")
        return cache_path

    except Exception as e:
        print(f"[RefAudio] Download error for {surah}:{ayah}: {e}")
        return None


def extract_mfcc(audio_path: str) -> np.ndarray:
    """
    Audio file se MFCC features extract karo.

    Returns:
        MFCC feature matrix (n_mfcc x time_frames)
    """
    try:
        # Load audio at 16kHz mono
        y, sr = librosa.load(audio_path, sr=16000, mono=True)

        # Trim silence from start/end
        y, _ = librosa.effects.trim(y, top_db=25)

        # Extract MFCCs
        mfccs = librosa.feature.mfcc(
            y=y, sr=sr,
            n_mfcc=N_MFCC,
            hop_length=HOP_LENGTH,
            n_fft=N_FFT,
        )

        # Normalize each MFCC coefficient
        mfccs = (mfccs - np.mean(mfccs, axis=1, keepdims=True)) / (
            np.std(mfccs, axis=1, keepdims=True) + 1e-8
        )

        return mfccs.T  # Transpose: (time_frames x n_mfcc) for DTW

    except Exception as e:
        print(f"[MFCC] Extraction error: {e}")
        return None


def compute_pronunciation_score(
    user_audio_path: str,
    surah: int,
    ayah: int,
    reciter: str = None,
) -> dict:
    """
    User ki recitation ko reference audio se compare karo using MFCC + DTW.

    Dynamic Time Warping (DTW) use karta hai — yeh alag-alag speed pe
    padding/recitation ko bhi handle karta hai accurately.

    Args:
        user_audio_path: User ke recorded audio ka path
        surah: Surah number
        ayah: Ayah number
        reciter: Reference reciter (default: Alafasy)

    Returns:
        dict with:
            - score: 0-100 (pronunciation similarity percentage)
            - dtw_distance: raw DTW distance (lower = better)
            - reference_available: bool
    """
    # Step 1: Reference audio download/cache
    ref_path = download_reference_audio(surah, ayah, reciter)
    if ref_path is None:
        return {
            "score": None,
            "dtw_distance": None,
            "reference_available": False,
        }

    # Step 2: MFCC extract karo dono se
    ref_mfcc = extract_mfcc(ref_path)
    user_mfcc = extract_mfcc(user_audio_path)

    if ref_mfcc is None or user_mfcc is None:
        return {
            "score": None,
            "dtw_distance": None,
            "reference_available": True,
        }

    # Step 3: DTW distance calculate karo
    try:
        distance, _ = fastdtw(ref_mfcc, user_mfcc, dist=cosine_distance)

        # Normalize distance to a 0-100 score
        # DTW distance varies widely, so we use a sigmoid-like mapping
        # Lower distance = higher score
        # Typical good match: distance < 50, bad: > 200
        max_reasonable_distance = 300.0
        normalized = min(distance / max_reasonable_distance, 1.0)
        score = round((1.0 - normalized) * 100, 2)
        score = max(0.0, min(100.0, score))

        return {
            "score": score,
            "dtw_distance": round(distance, 4),
            "reference_available": True,
        }

    except Exception as e:
        print(f"[DTW] Computation error: {e}")
        return {
            "score": None,
            "dtw_distance": None,
            "reference_available": True,
        }


def compute_surah_pronunciation(
    user_audio_path: str,
    surah: int,
    start_ayah: int = 1,
    end_ayah: int = None,
    reciter: str = None,
) -> dict:
    """
    Multiple ayaat ke liye aggregate pronunciation score.

    Note: Yeh tab better kaam karta hai jab har ayah ka alag audio ho.
    Agar ek hi audio mein puri surah hai, toh overall score deta hai
    pehli ayah ke reference se compare karke.

    Returns:
        dict with overall_score
    """
    # Single audio file ke liye: pehli ayah se compare karo as representative
    result = compute_pronunciation_score(
        user_audio_path, surah, start_ayah, reciter
    )

    return {
        "overall_pronunciation_score": result["score"],
        "dtw_distance": result["dtw_distance"],
        "reference_available": result["reference_available"],
        "note": "Score is based on first ayah reference comparison for full recitation audio.",
    }
