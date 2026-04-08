"""
QiraatAI — FastAPI Backend
--------------------------
Main API server for Quran recitation analysis.
Flutter app yahan se connect karta hai.
"""

from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

from database import SessionLocal, QuranWord, SurahInfo, UserSession
from models.schemas import (
    RecitationResponse,
    SurahItem,
    QuranWordItem,
    SessionCreate,
    SessionRead,
    WordAnalysis,
)
from services.whisper_service import transcribe_audio, get_model
from services.compare_service import compare_words

load_dotenv()

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QiraatAI API",
    description="Quran Recitation Analysis API powered by OpenAI Whisper",
    version="1.0.0",
)

# CORS — Flutter app ko connect karne ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup: Whisper model pehle se load kar lo ───────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("=" * 50)
    print("  QiraatAI Backend Starting...")
    print("=" * 50)
    get_model()  # Singleton — sirf ek baar load hoga
    print("[Server] Ready to receive recitations!")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 50)


# ── DB Dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def home():
    return {
        "app": "QiraatAI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# ── 1. Surahs List ────────────────────────────────────────────────────────────
@app.get("/api/v1/surahs", response_model=List[SurahItem], tags=["Quran Data"])
def get_surahs(db: Session = Depends(get_db)):
    """
    Aakhri 10 Surahs ki complete list return karta hai.
    Flutter app is se surah selection screen banati hai.
    """
    surahs = db.query(SurahInfo).order_by(SurahInfo.surah_no).all()
    if not surahs:
        # Agar surah_info table khali hai toh default data return karo
        return _default_surahs()
    return surahs


def _default_surahs():
    """Fallback: agar surah_info table khali ho."""
    data = [
        {"surah_no": 105, "name_arabic": "الفيل",     "name_english": "Al-Feel",     "name_urdu": "الفیل",    "total_verses": 5},
        {"surah_no": 106, "name_arabic": "قريش",      "name_english": "Quraysh",     "name_urdu": "قریش",     "total_verses": 4},
        {"surah_no": 107, "name_arabic": "الماعون",   "name_english": "Al-Ma'un",    "name_urdu": "الماعون",  "total_verses": 7},
        {"surah_no": 108, "name_arabic": "الكوثر",    "name_english": "Al-Kawthar",  "name_urdu": "الکوثر",   "total_verses": 3},
        {"surah_no": 109, "name_arabic": "الكافرون",  "name_english": "Al-Kafirun",  "name_urdu": "الکافرون", "total_verses": 6},
        {"surah_no": 110, "name_arabic": "النصر",     "name_english": "An-Nasr",     "name_urdu": "النصر",    "total_verses": 3},
        {"surah_no": 111, "name_arabic": "المسد",     "name_english": "Al-Masad",    "name_urdu": "المسد",    "total_verses": 5},
        {"surah_no": 112, "name_arabic": "الإخلاص",  "name_english": "Al-Ikhlas",   "name_urdu": "الاخلاص",  "total_verses": 4},
        {"surah_no": 113, "name_arabic": "الفلق",     "name_english": "Al-Falaq",    "name_urdu": "الفلق",    "total_verses": 5},
        {"surah_no": 114, "name_arabic": "الناس",     "name_english": "An-Nas",      "name_urdu": "الناس",    "total_verses": 6},
    ]
    return [SurahItem(**d) for d in data]


# ── 2. Surah Words (ayah-wise) ────────────────────────────────────────────────
@app.get("/api/v1/surah/{surah_id}", tags=["Quran Data"])
def get_surah_words(surah_id: int, db: Session = Depends(get_db)):
    """
    Kisi bhi Surah ke tamam alfaaz (Ayah number ke sath) return karta hai.
    Flutter app is se text display screen banati hai.
    """
    if surah_id < 105 or surah_id > 114:
        raise HTTPException(
            status_code=400,
            detail="Sirf Surah 105-114 available hain (Proof of Concept).",
        )

    words = (
        db.query(QuranWord)
        .filter(QuranWord.surah_no == surah_id)
        .order_by(QuranWord.ayah_no, QuranWord.word_position)
        .all()
    )

    if not words:
        raise HTTPException(
            status_code=404,
            detail=f"Surah {surah_id} database mein nahi mili. Pehle fetch_and_store.py chalayein.",
        )

    # Ayah-wise group karke return karo
    ayahs = {}
    for w in words:
        ayah_key = w.ayah_no
        if ayah_key not in ayahs:
            ayahs[ayah_key] = []
        ayahs[ayah_key].append({"word": w.word_arabic, "position": w.word_position})

    return {
        "surah_id": surah_id,
        "total_words": len(words),
        "ayahs": ayahs,
    }


# ── 3. MAIN ENDPOINT: Analyze Recitation ─────────────────────────────────────
@app.post("/api/v1/analyze-recitation", response_model=RecitationResponse, tags=["Analysis"])
async def analyze_recitation(
    surah_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    **Main Endpoint** — Flutter app yahan audio bhejti hai aur result wapis aata hai.

    - Audio file upload karo (WAV/MP3/M4A)
    - Whisper AI Arabic text transcribe karta hai
    - Word-by-word comparison hota hai
    - Har lafz ka correct/incorrect status milta hai
    - Accuracy % milti hai
    """
    # ── Validation ──────────────────────────────────────────────────────────
    if surah_id < 105 or surah_id > 114:
        raise HTTPException(
            status_code=400,
            detail="Sirf Surah 105-114 available hain.",
        )

    # ── DB se correct words nikaalo ──────────────────────────────────────────
    db_words = (
        db.query(QuranWord)
        .filter(QuranWord.surah_no == surah_id)
        .order_by(QuranWord.ayah_no, QuranWord.word_position)
        .all()
    )
    if not db_words:
        raise HTTPException(
            status_code=404,
            detail=f"Surah {surah_id} database mein nahi mili.",
        )

    correct_words = [w.word_arabic for w in db_words]
    correct_text = " ".join(correct_words)

    # ── Audio file temporarily save karo ────────────────────────────────────
    ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    temp_filename = f"temp_{uuid.uuid4().hex}{ext}"

    try:
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())

        # ── Whisper Transcription ────────────────────────────────────────────
        print(f"[Whisper] Transcribing Surah {surah_id}...")
        transcribed_text = transcribe_audio(temp_filename)
        print(f"[Whisper] Result: {transcribed_text[:80]}...")

        user_words = transcribed_text.split()

        # ── Word-by-Word Comparison ──────────────────────────────────────────
        word_analysis, accuracy = compare_words(correct_words, user_words)
        print(f"[Compare] Accuracy: {accuracy}%")

        # ── Session History Save karo ────────────────────────────────────────
        session = UserSession(
            surah_id=surah_id,
            accuracy_score=accuracy,
            recited_text=transcribed_text,
            timestamp=datetime.utcnow(),
        )
        db.add(session)
        db.commit()

        return RecitationResponse(
            status="success",
            surah_id=surah_id,
            accuracy=accuracy,
            transcribed_text=transcribed_text,
            original_text=correct_text,
            word_analysis=word_analysis,
        )

    except Exception as e:
        print(f"[Error] analyze-recitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Temp file delete karo
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


# ── 4. Session History ────────────────────────────────────────────────────────
@app.get("/api/v1/sessions", response_model=List[SessionRead], tags=["History"])
def get_sessions(limit: int = 20, db: Session = Depends(get_db)):
    """
    User ki pichli recitation sessions return karta hai.
    Flutter app is se Progress Tracking screen banati hai.
    """
    sessions = (
        db.query(UserSession)
        .order_by(UserSession.timestamp.desc())
        .limit(limit)
        .all()
    )
    return sessions


@app.post("/api/v1/sessions", response_model=SessionRead, tags=["History"])
def save_session(session_data: SessionCreate, db: Session = Depends(get_db)):
    """
    Manually session save karna (agar Flutter app locally save karna chahay).
    """
    session = UserSession(
        surah_id=session_data.surah_id,
        accuracy_score=session_data.accuracy_score,
        recited_text=session_data.recited_text,
        timestamp=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.delete("/api/v1/sessions/{session_id}", tags=["History"])
def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Koi purani session delete karo."""
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session nahi mili.")
    db.delete(session)
    db.commit()
    return {"message": f"Session {session_id} delete ho gayi."}


# ── 5. Stats (Bonus) ──────────────────────────────────────────────────────────
@app.get("/api/v1/stats", tags=["History"])
def get_stats(db: Session = Depends(get_db)):
    """
    User ki overall stats return karta hai.
    """
    sessions = db.query(UserSession).all()
    if not sessions:
        return {"total_sessions": 0, "average_accuracy": 0, "best_accuracy": 0}

    scores = [s.accuracy_score for s in sessions]
    return {
        "total_sessions": len(sessions),
        "average_accuracy": round(sum(scores) / len(scores), 2),
        "best_accuracy": round(max(scores), 2),
        "worst_accuracy": round(min(scores), 2),
    }