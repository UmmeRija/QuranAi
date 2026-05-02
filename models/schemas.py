from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# ── Word-level analysis ──────────────────────────────────────────────────────
class WordAnalysis(BaseModel):
    correct_word: str  # Original word from Quran
    user_word: Optional[str] = None # What the user said
    status: str        # "match" | "incorrect" | "missing" | "extra"
    position: int


# ── Ayah-level analysis (NEW — Tanzil comparison) ────────────────────────────
class AyahAnalysis(BaseModel):
    ayah_no: int
    text_accuracy: float
    pronunciation_score: Optional[float] = None
    missing_words: List[str] = []
    incorrect_words: List[str] = []


# ── Full recitation analysis response ────────────────────────────────────────
class RecitationResponse(BaseModel):
    status: str
    surah_id: int
    start_ayah: Optional[int] = None
    end_ayah: Optional[int] = None
    accuracy: float
    transcribed_text: str
    original_text: str
    word_analysis: List[WordAnalysis]
    # New fields for enhanced analysis
    pronunciation_score: Optional[float] = None      # 0-100 from MFCC/DTW
    ayah_analysis: Optional[List[AyahAnalysis]] = None  # Per-ayah breakdown


# ── Surah list item ───────────────────────────────────────────────────────────
class SurahItem(BaseModel):
    surah_no: int
    name_arabic: str
    name_english: str
    name_urdu: str
    total_verses: int

    class Config:
        from_attributes = True


# ── Single word row ───────────────────────────────────────────────────────────
class QuranWordItem(BaseModel):
    id: int
    surah_no: int
    ayah_no: int
    word_arabic: str
    word_position: int

    class Config:
        from_attributes = True


# ── Session (history) ─────────────────────────────────────────────────────────
class SessionCreate(BaseModel):
    surah_id: int
    accuracy_score: float
    recited_text: str


class SessionRead(BaseModel):
    id: int
    surah_id: int
    surah_name: Optional[str] = "Surah"
    accuracy_score: float
    recited_text: str
    timestamp: datetime


    class Config:
        from_attributes = True
