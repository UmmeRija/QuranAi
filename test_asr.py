import os
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import librosa

def test_transcription(file_path):
    model_id = "tarteel-ai/whisper-base-ar-quran"
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    audio, _ = librosa.load(file_path, sr=16000)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt").to(device)

    # No prompt
    predicted_ids = model.generate(inputs["input_features"], max_new_tokens=448)
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)
    print(f"Result (No prompt): {transcription[0]}")

    # With prompt (Surah Fatehah start)
    prompt = "الحمد لله رب العالمين"
    prompt_ids = processor.get_prompt_ids(prompt, return_tensors="pt").to(device)
    predicted_ids_p = model.generate(inputs["input_features"], prompt_ids=prompt_ids, max_new_tokens=300)
    transcription_p = processor.batch_decode(predicted_ids_p, skip_special_tokens=True)
    print(f"Result (With prompt): {transcription_p[0]}")

# Use one of the 1.7MB files (long recitation)
test_file = "temp_89d708d0e380483fb3bdd5e1fed2fada_cleaned.wav"
if os.path.exists(test_file):
    test_transcription(test_file)
else:
    print("Test file not found")
