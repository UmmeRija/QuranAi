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
from services.asr_service import transcribe_audio, get_pipeline
from services.compare_service import compare_words, compare_ayah_text
from services.tanzil_service import store_tanzil_in_db, get_surah_text
from services.audio_reference_service import compute_pronunciation_score

load_dotenv()

# â”€â”€ App Setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = FastAPI(
    title="QiraatAI API",
    description="Quran Recitation Analysis â€” Tarteel AI + Tanzil + EveryAyah",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# â”€â”€ Startup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("  QiraatAI Backend v2.1 Starting...")
    print("  [Tarteel AI ASR + Tanzil + EveryAyah]")
    print("=" * 60)
    init_db()
    try:
        store_tanzil_in_db()
        print("[Startup] Tanzil reference text ready.")
    except Exception as e:
        print(f"[Startup] Tanzil setup warning: {e}")
    get_pipeline()
    print("[Server] Ready to receive recitations!")
    print("=" * 60)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  ENDPOINTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.get("/", tags=["Health"])
def home():
    return {
        "app": "QiraatAI",
        "version": "2.1.0",
        "engine": "Tarteel AI (whisper-base-ar-quran)",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/v1/surahs", response_model=List[SurahItem], tags=["Quran Data"])
def get_surahs(db: Session = Depends(get_db)):
    surahs = db.query(SurahInfo).order_by(SurahInfo.surah_no).all()
    if not surahs:
        raise HTTPException(status_code=404, detail="Surah metadata nahi mili.")
    return surahs


@app.get("/api/v1/surah/{surah_id}", tags=["Quran Data"])
def get_surah_words(surah_id: int, db: Session = Depends(get_db)):
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(status_code=400, detail="Sirf Surah 1-114 available hain.")

    words = (
        db.query(QuranWord)
        .filter(QuranWord.surah_no == surah_id)
        .order_by(QuranWord.ayah_no, QuranWord.word_position)
        .all()
    )
    if not words:
        raise HTTPException(status_code=404, detail=f"Surah {surah_id} database mein nahi mili.")

    ayahs = {}
    for w in words:
        if w.ayah_no not in ayahs:
            ayahs[w.ayah_no] = []
        ayahs[w.ayah_no].append({"word": w.word_arabic, "position": w.word_position})

    return {"surah_id": surah_id, "total_words": len(words), "ayahs": ayahs}


# â”€â”€ MAIN ENDPOINT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.post("/api/v1/analyze-recitation", response_model=RecitationResponse, tags=["Analysis"])
async def analyze_recitation(
    surah_id: int = Form(...),
    ayah_no: Optional[int] = Form(None),
    start_ayah: Optional[int] = Form(None),
    end_ayah: Optional[int] = Form(None),
    include_pronunciation: Optional[bool] = Form(False),
    save_session: Optional[bool] = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Main Endpoint â€” Flutter app audio bhejti hai, word-by-word analysis wapis aata hai.

    KEY FIX (v2.1):
    - ayah_no=1 bhejne par sirf ayah 1 nahi, PURI SURAH check hoti hai
    - Flutter ko ab start_ayah + end_ayah dono dene ki zaroorat nahi
    - Agar sirf ayah_no bheja toh bhi poori surah ka context milta hai
    """
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(status_code=400, detail="Sirf Surah 1-114 available hain.")

    # â”€â”€ Range Resolution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Flutter sirf ayah_no=1 bhejta hai â€” hum isko surah ki last ayah tak extend karte hain
    # Agar Flutter ne explicit start+end diya toh woh use karo

    if start_ayah is None and ayah_no is not None:
        start_ayah = ayah_no

    # â­ KEY FIX: Agar end_ayah nahi diya â€” puri surah lo
    if end_ayah is None:
        # DB se is surah ki last ayah number nikaalo
        last_word = (
            db.query(QuranWord)
            .filter(QuranWord.surah_no == surah_id, QuranWord.ayah_no > 0)
            .order_by(QuranWord.ayah_no.desc())
            .first()
        )
        end_ayah = last_word.ayah_no if last_word else (start_ayah or 7)
        print(f"[Route] end_ayah not provided â€” using surah last ayah: {end_ayah}")

    if start_ayah is None:
        start_ayah = 1

    print(f"[Route] Surah {surah_id}, Ayaat {start_ayah}â€“{end_ayah}")

    # â”€â”€ DB se correct words nikaalo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Ayah 0 = Bismillah/Intro â€” start_ayah==1 ke liye include karo
    fetch_start = 0 if start_ayah == 1 else start_ayah

    db_words = (
        db.query(QuranWord)
        .filter(
            QuranWord.surah_no == surah_id,
            QuranWord.ayah_no >= fetch_start,
            QuranWord.ayah_no <= end_ayah,
        )
        .order_by(QuranWord.ayah_no, QuranWord.word_position)
        .all()
    )

    if not db_words:
        raise HTTPException(
            status_code=404,
            detail=f"Surah {surah_id} ayaat {start_ayah}-{end_ayah} database mein nahi mili."
        )

    correct_words = [w.word_arabic for w in db_words]
    correct_text = " ".join(correct_words)
    intro_word_count = len([w for w in db_words if w.ayah_no == 0])

    print(f"[Route] Total correct words loaded: {len(correct_words)} (intro: {intro_word_count})")

    # â”€â”€ Audio Save â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    temp_filename = f"temp_{uuid.uuid4().hex}{ext}"

    try:
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())

        # â”€â”€ Step 1: ASR Transcription â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        print(f"[ASR] Transcribing Surah {surah_id} ({start_ayah}-{end_ayah})...")
        transcribed_text = transcribe_audio(temp_filename)
        print(f"[ASR] Result: '{transcribed_text[:100]}...'")

        if not transcribed_text:
            # ASR ne kuch nahi pakda â€” empty result handle karo
            print("[ASR] WARNING: Empty transcription!")
            return RecitationResponse(
                status="error",
                surah_id=surah_id,
                start_ayah=start_ayah,
                end_ayah=end_ayah,
                accuracy=0.0,
                transcribed_text="",
                original_text=correct_text,
                word_analysis=[
                    WordAnalysis(
                        correct_word=w,
                        user_word=None,
                        status="missing",
                        position=i + 1,
                    )
                    for i, w in enumerate(correct_words)
                ],
                pronunciation_score=None,
                ayah_analysis=None,
            )

        user_words = transcribed_text.split()

        # â”€â”€ Step 2: Word-by-Word Comparison â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        word_analysis, accuracy = compare_words(
            correct_words,
            user_words,
            intro_word_count=intro_word_count,
        )
        print(f"[Compare] Accuracy: {accuracy}% ({len(user_words)} recited vs {len(correct_words)} expected)")

        # â”€â”€ Step 3: Ayah-level Analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        ayah_analysis_list = []
        tanzil_texts = get_surah_text(surah_id, start_ayah, end_ayah, db)

        if tanzil_texts:
            for ayah_num, ref_text in tanzil_texts.items():
                ayah_result = compare_ayah_text(ref_text, transcribed_text)

                ayah_pron_score = None
                if include_pronunciation:
                    try:
                        pron_result = compute_pronunciation_score(temp_filename, surah_id, ayah_num)
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

        # â”€â”€ Step 4: Overall Pronunciation Score â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        overall_pron_score = None
        if include_pronunciation:
            try:
                pron = compute_pronunciation_score(temp_filename, surah_id, start_ayah)
                overall_pron_score = pron.get("score")
            except Exception as e:
                print(f"[Pronunciation] Overall error: {e}")

        # ── Step 5: Session Save ─────────────────────────────────────────────
        if save_session:
            new_session = UserSession(
                surah_id=surah_id,
                accuracy_score=accuracy / 100.0,
                recited_text=transcribed_text,
                timestamp=datetime.utcnow(),
            )
            db.add(new_session)
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
            ayah_analysis=ayah_analysis_list,
        )

    except Exception as e:
        print(f"[Analyze] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


# â”€â”€ Session History â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/v1/sessions", response_model=List[SessionRead], tags=["History"])
def get_sessions(limit: int = 20, db: Session = Depends(get_db)):
    results = (
        db.query(UserSession, SurahInfo.name_english)
        .outerjoin(SurahInfo, UserSession.surah_id == SurahInfo.surah_no)
        .order_by(UserSession.timestamp.desc())
        .limit(limit)
        .all()
    )
    
    sessions = []
    for s, name in results:
        s.surah_name = name or f"Surah {s.surah_id}"
        sessions.append(s)
    return sessions


@app.post("/api/v1/sessions", response_model=SessionRead, tags=["History"])
def save_session(session_data: SessionCreate, db: Session = Depends(get_db)):
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
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session nahi mili.")
    db.delete(session)
    db.commit()
    return {"message": f"Session {session_id} delete ho gayi."}


@app.get("/api/v1/stats", tags=["History"])
def get_stats(db: Session = Depends(get_db)):
    sessions = db.query(UserSession).order_by(UserSession.timestamp.desc()).all()
    
    if not sessions:
        return {
            "total_sessions": 0,
            "average_accuracy": 0,
            "best_accuracy": 0,
            "streak": 0,
            "last_session": None,
            "weekly_progress": [0] * 7,
            "total_words": 0,
            "total_surahs": 0,
            "velocity_data": []
        }

    scores = [s.accuracy_score for s in sessions]
    
    # Calculate Streak
    streak = 0
    today = datetime.utcnow().date()
    
    # Get unique dates of sessions in descending order
    session_dates = sorted(list(set(s.timestamp.date() for s in sessions)), reverse=True)
    
    if session_dates:
        from datetime import timedelta
        check_date = today
        # If user didn't practice today, start checking from yesterday
        if check_date not in session_dates:
            check_date -= timedelta(days=1)
        
        date_set = set(session_dates)
        while check_date in date_set:
            streak += 1
            check_date -= timedelta(days=1)

    # Last Session details
    last_s = sessions[0]
    surah = db.query(SurahInfo).filter(SurahInfo.surah_no == last_s.surah_id).first()
    last_session_data = {
        "surah_name": surah.name_english if surah else f"Surah {last_s.surah_id}",
        "surah_id": last_s.surah_id,
        "accuracy": last_s.accuracy_score,
        "timestamp": last_s.timestamp.isoformat()
    }

    # Detailed Stats for Progress Screen
    total_words = 0
    for s in sessions:
        if s.recited_text:
            total_words += len(s.recited_text.split())

    unique_surahs = len(set(s.surah_id for s in sessions))

    from datetime import timedelta
    weekly_progress = []
    velocity_data = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        day_sessions = [s.accuracy_score for s in sessions if s.timestamp.date() == target_date]
        avg_acc = sum(day_sessions) / len(day_sessions) if day_sessions else 0
        weekly_progress.append(round(avg_acc, 2))
        velocity_data.append({
            "day": target_date.strftime("%a"),
            "accuracy": round(avg_acc, 2),
            "sessions": len(day_sessions)
        })

    return {
        "total_sessions": len(sessions),
        "total_words": total_words,
        "total_surahs": unique_surahs,
        "average_accuracy": round(sum(scores) / len(scores), 2),
        "best_accuracy": round(max(scores), 2),
        "streak": streak,
        "last_session": last_session_data,
        "weekly_progress": weekly_progress,
        "velocity_data": velocity_data,
    }

