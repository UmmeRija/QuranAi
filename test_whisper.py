import whisper

print("Loading the model...")
model = whisper.load_model("tiny")

# We will tell it to read a non-existent file just to see if FFmpeg is installed!
print("Testing audio processor...")
try:
    # This will fail because the file doesn't exist, but it tells us if FFmpeg works!
    result = model.transcribe("non_existent_audio.mp3")
except FileNotFoundError as e:
    if "ffmpeg" in str(e).lower() or "[WinError 2]" in str(e):
         print("\n❌ FFmpeg is missing. We need to install it!")
    else:
         print("\n✅ FFmpeg is working great! (It just couldn't find our test file).")
except Exception as e:
    print(f"Got another error: {e}")