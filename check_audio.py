import os
import numpy as np
import librosa

def check_audio_energy(file_path):
    try:
        y, sr = librosa.load(file_path, sr=16000)
        rms = np.sqrt(np.mean(y**2))
        print(f"File: {file_path}")
        print(f"Duration: {librosa.get_duration(y=y, sr=sr):.2f}s")
        print(f"RMS Energy: {rms:.6f}")
        if rms < 0.001:
            print("WARNING: Audio seems very quiet or silent!")
    except Exception as e:
        print(f"Error checking {file_path}: {e}")

# Find most recent temp file
files = [f for f in os.listdir(".") if f.startswith("temp_") and f.endswith(".wav")]
if files:
    latest_file = max(files, key=os.path.getmtime)
    print(f"Latest file: {latest_file}")
    check_audio_energy(latest_file)
else:
    print("No temp files found")
