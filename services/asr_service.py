"""
ASR Service (Quran-Specialized)
--------------------------------
Tarteel AI ka whisper-base-ar-quran model use karta hai.
"""

import os
import numpy as np
import torch
import librosa
from pydub import AudioSegment
import noisereduce as nr
from dotenv import load_dotenv

load_dotenv()

_processor = None
_model = None
_device = None


def get_model():
    global _processor, _model, _device

    if _model is None:
        from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

        model_id = os.getenv("ASR_MODEL", "tarteel-ai/whisper-base-ar-quran")
        print(f"[ASR] Loading Tarteel model '{model_id}' — please wait...")

        _processor = AutoProcessor.from_pretrained(model_id)
        _model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id)

        # Fix outdated generation config
        _model.generation_config.forced_decoder_ids = None
        _model.generation_config.suppress_tokens = []

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _model.to(_device)

        print(f"[ASR] Model loaded on '{_device}' successfully!")

    return _processor, _model, _device


def clean_audio(file_path: str) -> str:
    try:
        print(f"[Audio] Cleaning: {file_path}")
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        samples = np.array(audio.get_array_of_samples())

        reduced_noise = nr.reduce_noise(
            y=samples.astype(np.float32),
            sr=16000,
            prop_decrease=0.60
        )

        cleaned_audio = audio._spawn(reduced_noise.astype(np.int16))
        cleaned_audio = cleaned_audio.high_pass_filter(80)
        cleaned_audio = cleaned_audio.normalize()

        base, ext = os.path.splitext(file_path)
        cleaned_file_path = f"{base}_cleaned.wav"
        cleaned_audio.export(cleaned_file_path, format="wav")

        return cleaned_file_path
    except Exception as e:
        print(f"[Audio] Cleaning error: {e}")
        return file_path


def transcribe_audio(file_path: str, initial_prompt: str = None) -> str:
    # Step 1: Clean audio
    cleaned_path = clean_audio(file_path)

    # Step 2: Load audio
    try:
        audio_array, sr = librosa.load(cleaned_path, sr=16000, mono=True)
    except Exception as e:
        print(f"[ASR] Librosa load error: {e}")
        temp_wav = cleaned_path.replace(".wav", "_conv.wav")
        audio_seg = AudioSegment.from_file(cleaned_path)
        audio_seg = audio_seg.set_frame_rate(16000).set_channels(1)
        audio_seg.export(temp_wav, format="wav")
        audio_array, sr = librosa.load(temp_wav, sr=16000, mono=True)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    # Step 3: Get model
    processor, model, device = get_model()

    # Step 4: Process audio
    inputs = processor(
        audio_array,
        sampling_rate=16000,
        return_tensors="pt"
    ).to(device)

    # Step 5: Generate — forced_decoder_ids manually set karo
    with torch.no_grad():
        forced_decoder_ids = processor.get_decoder_prompt_ids(
            language="ar",
            task="transcribe"
        )
        predicted_ids = model.generate(
            inputs["input_features"],
            forced_decoder_ids=forced_decoder_ids,
            max_new_tokens=200,
        )

    # Step 6: Decode
    transcription = processor.batch_decode(
        predicted_ids,
        skip_special_tokens=True
    )

    # Cleanup
    if cleaned_path != file_path and os.path.exists(cleaned_path):
        os.remove(cleaned_path)

    result = transcription[0].strip() if transcription else ""
    print(f"[ASR] Transcribed: {result[:80]}...")
    return result