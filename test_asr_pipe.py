import os
import torch
from transformers import pipeline

def test_pipeline(file_path):
    model_id = "tarteel-ai/whisper-base-ar-quran"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"Testing pipeline on {file_path}...")
    # Use pipeline for automatic chunking
    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_id,
        device=device,
        chunk_length_s=30,
    )

    # Transcription with chunking
    result = pipe(file_path, generate_kwargs={"max_new_tokens": 400})
    print(f"Result (Pipeline Chunking): {result['text']}")

# Use one of the 1.7MB files
test_file = "temp_89d708d0e380483fb3bdd5e1fed2fada_cleaned.wav"
if os.path.exists(test_file):
    test_pipeline(test_file)
else:
    print("Test file not found")
