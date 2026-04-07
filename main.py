from fastapi import FastAPI, Depends, File, UploadFile
from sqlalchemy.orm import Session
from database import SessionLocal, QuranWord
import whisper
import os
import difflib

app = FastAPI()

# 1. AI Model Setup
print("Loading Whisper AI model...")
model = whisper.load_model("tiny")
print("Whisper AI loaded successfully!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def home():
    return {"message": "Quran Word-by-Word & AI API is Running!"}

# 2. Database Fetching Endpoint
@app.get("/surah/{surah_id}")
def get_surah_data(surah_id: int, db: Session = Depends(get_db)):
    words = db.query(QuranWord).filter(QuranWord.surah_no == surah_id).all()
    if not words:
        return {"error": "Surah not found or invalid Surah ID."}
    return words

# 3. AI Transcription + Comparison Endpoint
@app.post("/recite")
async def process_recitation(surah_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # A. Database se words nikaalna (Fix: word_arabic use kiya hai)
    db_words = db.query(QuranWord).filter(QuranWord.surah_no == surah_id).all()
    if not db_words:
        return {"status": "error", "message": f"Surah {surah_id} database mein nahi mili."}
    
    # Check karein ke column ka naam 'word_arabic' hi hai
    correct_words = [w.word_arabic for w in db_words]
    correct_text = " ".join(correct_words)
    
    # B. Audio file save karna
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        # C. AI Transcription
        print(f"AI is listening to Surah {surah_id}...")
        result = model.transcribe(temp_filename, language="ar")
        transcribed_text = result["text"].strip()
        user_words = transcribed_text.split()
        
        # D. Accuracy Calculation
        matcher = difflib.SequenceMatcher(None, correct_words, user_words)
        accuracy_score = round(matcher.ratio() * 100, 2)
        
        return {
            "status": "success",
            "accuracy": f"{accuracy_score}%",
            "original_text": correct_text,
            "your_recitation": transcribed_text,
            "match_details": {
                "correct_word_count": len(correct_words),
                "user_word_count": len(user_words)
            }
        }
    except Exception as e:
        # Terminal mein error print karein taake pata chale kya masla hai
        print(f"Error occurred: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)