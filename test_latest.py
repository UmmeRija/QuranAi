import os
import torch
from transformers import pipeline

def test_latest():
    files = [f for f in os.listdir(".") if f.startswith("temp_") and f.endswith(".wav")]
    if not files:
        print("No files")
        return
    latest_file = max(files, key=os.path.getmtime)
    print(f"Testing: {latest_file}")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = pipeline(
        "automatic-speech-recognition",
        model="tarteel-ai/whisper-base-ar-quran",
        device=device,
    )

    result = pipe(latest_file, generate_kwargs={"language": "ar", "task": "transcribe"})
    print(f"Result: [{result['text']}]")

test_latest()
