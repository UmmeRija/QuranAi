from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./quran.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class QuranWord(Base):
    __tablename__ = "quran_words"

    id = Column(Integer, primary_key=True, index=True)
    surah_no = Column(Integer)
    ayah_no = Column(Integer)
    word_arabic = Column(String)
    word_position = Column(Integer)