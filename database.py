from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quran.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Table 1: Quran Words ────────────────────────────────────────────────────
class QuranWord(Base):
    __tablename__ = "quran_words"

    id            = Column(Integer, primary_key=True, index=True)
    surah_no      = Column(Integer, index=True)
    ayah_no       = Column(Integer)
    ruku_no       = Column(Integer, index=True)   # Added for portion selection
    page_no       = Column(Integer, index=True)   # Added for 15-line page concept
    line_no       = Column(Integer)               # Added for precise tracking
    word_arabic   = Column(String)
    word_position = Column(Integer)


# ── Table 2: Surah Info ─────────────────────────────────────────────────────
class SurahInfo(Base):
    __tablename__ = "surah_info"

    id             = Column(Integer, primary_key=True, index=True)
    surah_no       = Column(Integer, unique=True, index=True)
    name_arabic    = Column(String)
    name_english   = Column(String)
    name_urdu      = Column(String)
    total_verses   = Column(Integer)


# ── Table 3: User Sessions (Recitation History) ─────────────────────────────
class UserSession(Base):
    __tablename__ = "user_sessions"

    id             = Column(Integer, primary_key=True, index=True)
    surah_id       = Column(Integer, index=True)
    accuracy_score = Column(Float)
    recited_text   = Column(String)
    timestamp      = Column(DateTime, default=datetime.utcnow)


# Create all tables on startup
Base.metadata.create_all(bind=engine)