"""
QiraatAI — FastAPI Backend (v2.0)
----------------------------------
Quran recitation analysis powered by:
- Tarteel AI (Quran-specialized ASR)
- Tanzil.net (Authoritative reference text)
- EveryAyah.com (Reference audio for pronunciation scoring)

Flutter app yahan se connect karta hai.
"""

from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

from database import SessionLocal, QuranWord, SurahInfo, UserSession, TanzilText, init_db
from models.schemas import (
    RecitationResponse,
    SurahItem,
    QuranWordItem,
    SessionCreate,
    SessionRead,
    WordAnalysis,
    AyahAnalysis,
)
from services.asr_service import transcribe_audio, get_model
from services.compare_service import compare_words, compare_ayah_text
from services.tanzil_service import store_tanzil_in_db, get_surah_text
from services.audio_reference_service import compute_pronunciation_score

load_dotenv()

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QiraatAI API",
    description="Quran Recitation Analysis — Tarteel AI + Tanzil + EveryAyah",
    version="2.0.0",
)

# CORS — Flutter app ko connect karne ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("  QiraatAI Backend v2.0 Starting...")
    print("  [Tarteel AI ASR + Tanzil + EveryAyah]")
    print("=" * 60)

    # 1. Database tables
    init_db()

    # 2. Tanzil reference text download + store
    try:
        store_tanzil_in_db()
        print("[Startup] Tanzil reference text ready.")
    except Exception as e:
        print(f"[Startup] Tanzil setup warning: {e}")

    # 3. ASR model load (singleton)
    get_model()

    print("[Server] Ready to receive recitations!")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 60)


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
        "version": "2.0.0",
        "engine": "Tarteel AI (whisper-base-ar-quran)",
        "status": "running",
        "docs": "/docs",
    }


# ── 1. Surahs List ────────────────────────────────────────────────────────────
@app.get("/api/v1/surahs", response_model=List[SurahItem], tags=["Quran Data"])
def get_surahs(db: Session = Depends(get_db)):
    """
    Tamam 114 Surahs ki complete list return karta hai.
    """
    surahs = db.query(SurahInfo).order_by(SurahInfo.surah_no).all()
    if not surahs:
        raise HTTPException(
            status_code=404, 
            detail="Surah metadata nahi mili. Pehle fetch_and_store.py chalayein."
        )
    return surahs


# ── 2. Surah Words (ayah-wise) ────────────────────────────────────────────────
@app.get("/api/v1/surah/{surah_id}", tags=["Quran Data"])
def get_surah_words(surah_id: int, db: Session = Depends(get_db)):
    """
    Kisi bhi Surah ke tamam alfaaz (Ayah number ke sath) return karta hai.
    Flutter app is se text display screen banati hai.
    """
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(
            status_code=400,
            detail="Sirf Surah 1-114 available hain.",
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
    ayah_no: Optional[int] = Form(None),    # Backward compatibility
    start_ayah: Optional[int] = Form(None), # Range start
    end_ayah: Optional[int] = Form(None),   # Range end
    include_pronunciation: Optional[bool] = Form(False),  # MFCC/DTW scoring
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    """
    **Main Endpoint** — Flutter app yahan audio bhejti hai aur result wapis aata hai.

    - `surah_id` (required): Surah number (1–114)
    - `ayah_no` (optional): Single ayah select karo
    - `start_ayah` / `end_ayah` (optional): Ayah range
    - `include_pronunciation` (optional): MFCC/DTW pronunciation scoring ON/OFF
    - Audio file upload karo (WAV/MP3/M4A)
    - **Tarteel AI** Arabic text transcribe karta hai (Quran-specialized)
    - Word-by-word + Ayah-level comparison hota hai
    - Pronunciation scoring (optional) — EveryAyah reference audio se
    """
    # ── Validation ──────────────────────────────────────────────────────────
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(status_code=400, detail="Sirf Surah 1-114 available hain.")

    # ── Param Mapping ───────────────────────────────────────────────────────
    if ayah_no is not None and start_ayah is None:
        start_ayah = ayah_no
        end_ayah = ayah_no
    
    if start_ayah is not None and end_ayah is None:
        end_ayah = start_ayah

    # ── DB se correct words nikaalo ──────────────────────────────────────────
    query = db.query(QuranWord).filter(QuranWord.surah_no == surah_id)

    if start_ayah is not None and end_ayah is not None:
        query = query.filter(QuranWord.ayah_no >= start_ayah, QuranWord.ayah_no <= end_ayah)

    db_words = query.order_by(QuranWord.ayah_no, QuranWord.word_position).all()

    if not db_words:
        raise HTTPException(status_code=404, detail="Requested portion database mein nahi mila.")

    correct_words = [w.word_arabic for w in db_words]
    correct_text = " ".join(correct_words)

    # ── Audio file temporarily save karo ────────────────────────────────────
    ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    temp_filename = f"temp_{uuid.uuid4().hex}{ext}"

    try:
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())

        # ── Step 1: Tarteel AI Transcription ─────────────────────────────────
        print(f"[Tarteel] Transcribing Surah {surah_id}...")
        transcribed_text = transcribe_audio(temp_filename)
        print(f"[Tarteel] Result: {transcribed_text[:80]}...")

        user_words = transcribed_text.split()

        # ── Step 2: Word-by-Word Comparison ──────────────────────────────────
        word_analysis, accuracy = compare_words(correct_words, user_words)
        print(f"[Compare] Word accuracy: {accuracy}%")

        # ── Step 3: Ayah-level Analysis (Tanzil reference) ───────────────────
        ayah_analysis_list = []
        tanzil_texts = get_surah_text(surah_id, start_ayah, end_ayah, db)

        if tanzil_texts:
            for ayah_num, ref_text in tanzil_texts.items():
                ayah_result = compare_ayah_text(ref_text, transcribed_text)
                
                ayah_pron_score = None
                # Step 4: Optional pronunciation scoring per-ayah
                if include_pronunciation:
                    try:
                        pron_result = compute_pronunciation_score(
                            temp_filename, surah_id, ayah_num
                        )
                        ayah_pron_score = pron_result.get("score")
                    except Exception as e:
                        print(f"[Pronunciation] Error for {surah_id}:{ayah_num}: {e}")

                ayah_analysis_list.append(AyahAnalysis(
                    ayah_no=ayah_num,
                    text_accuracy=ayah_result["accuracy"],
                    pronunciation_score=ayah_pron_score,
                    missing_words=ayah_result["missing_words"],
                    incorrect_words=ayah_result["incorrect_words"],
                ))

        # ── Step 5: Overall pronunciation score ─────────────────────────────
        overall_pron_score = None
        if include_pronunciation and start_ayah is not None:
            try:
                pron = compute_pronunciation_score(
                    temp_filename, surah_id, start_ayah
                )
                overall_pron_score = pron.get("score")
            except Exception as e:
                print(f"[Pronunciation] Overall error: {e}")

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
            start_ayah=start_ayah,
            end_ayah=end_ayah,
            accuracy=accuracy,
            transcribed_text=transcribed_text,
            original_text=correct_text,
            word_analysis=word_analysis,
            pronunciation_score=overall_pron_score,
            ayah_analysis=ayah_analysis_list if ayah_analysis_list else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Error] analyze-recitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
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