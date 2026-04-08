from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# ── Word-level analysis ──────────────────────────────────────────────────────
class WordAnalysis(BaseModel):
    word: str
    status: str        # "correct" | "incorrect" | "missing"
    position: int


# ── Full recitation analysis response ────────────────────────────────────────
class RecitationResponse(BaseModel):
    status: str
    surah_id: int
    accuracy: float
    transcribed_text: str
    original_text: str
    word_analysis: List[WordAnalysis]


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
    accuracy_score: float
    recited_text: str
    timestamp: datetime

    class Config:
        from_attributes = True
