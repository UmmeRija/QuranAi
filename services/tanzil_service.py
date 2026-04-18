"""
Tanzil Service
--------------
Tanzil.net se Quran ka Uthmani text (with full tashkeel/harakat) download
aur manage karta hai.

Tanzil.net sabse trusted aur verified digital Quran text source hai.
Format: surah_no|ayah_no|text (UTF-8)
"""

import os
import json
import requests
from sqlalchemy.orm import Session
from database import SessionLocal, TanzilText


# Tanzil download URL — Uthmani text with full tashkeel
TANZIL_DOWNLOAD_URL = (
 "https://api.alquran.cloud/v1/quran/quran-uthmani"
)

# Local cache path
TANZIL_CACHE_FILE = os.path.join("data", "tanzil_uthmani.txt")


def download_tanzil_text() -> str:
    """
    Tanzil.net se Uthmani Quran text download karo.
    Returns: local file path
    """
    os.makedirs("data", exist_ok=True)

    if os.path.exists(TANZIL_CACHE_FILE):
        print(f"[Tanzil] Using cached file: {TANZIL_CACHE_FILE}")
        return TANZIL_CACHE_FILE

    print("[Tanzil] Downloading Uthmani text from tanzil.net...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        resp = requests.get(TANZIL_DOWNLOAD_URL, headers=headers, timeout=30)
        resp.raise_for_status()

        with open(TANZIL_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(resp.text)

        print(f"[Tanzil] Downloaded and saved to {TANZIL_CACHE_FILE}")
        return TANZIL_CACHE_FILE

    except Exception as e:
        print(f"[Tanzil] Download error: {e}")
        raise


def parse_tanzil_file(file_path: str) -> list:
    """
    Tanzil JSON format parse karo.
    Supports legacy GitHub format and the new alquran.cloud API response.

    Returns: list of dicts [{surah_no, ayah_no, text}, ...]
    """
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "code" in data and "data" in data:
        data = data["data"]

    if isinstance(data, dict) and "surahs" in data:
        for surah in data["surahs"]:
            surah_no = surah.get("number")
            for ayah in surah.get("ayahs", []):
                ayah_no = ayah.get("numberInSurah") or ayah.get("number")
                text = ayah.get("text", "")
                if surah_no is None or ayah_no is None:
                    continue
                entries.append({
                    "surah_no": int(surah_no),
                    "ayah_no": int(ayah_no),
                    "text": text.strip(),
                })
        return entries

    if isinstance(data, dict):
        for surah_no_str, ayahs in data.items():
            if not isinstance(ayahs, dict):
                continue
            for ayah_no_str, text in ayahs.items():
                try:
                    entries.append({
                        "surah_no": int(surah_no_str),
                        "ayah_no": int(ayah_no_str),
                        "text": text.strip(),
                    })
                except (ValueError, AttributeError):
                    continue

    return entries


def store_tanzil_in_db(db: Session = None):
    """
    Tanzil text download karke database mein store karo.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Pehle se data hai toh skip karo
        existing = db.query(TanzilText).count()
        if existing > 0:
            print(f"[Tanzil] Database already has {existing} entries. Skipping.")
            return

        # Download karo
        file_path = download_tanzil_text()

        # Parse karo
        entries = parse_tanzil_file(file_path)
        print(f"[Tanzil] Parsed {len(entries)} ayahs.")

        # Store karo
        for entry in entries:
            db.add(TanzilText(
                surah_no=entry["surah_no"],
                ayah_no=entry["ayah_no"],
                text=entry["text"],
            ))

        db.commit()
        print(f"[Tanzil] Stored {len(entries)} ayahs in database.")

    except Exception as e:
        db.rollback()
        print(f"[Tanzil] Store error: {e}")
        raise
    finally:
        if close_db:
            db.close()


def get_ayah_text(surah_no: int, ayah_no: int, db: Session = None) -> str:
    """
    Kisi specific ayah ka Tanzil text return karo.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        row = db.query(TanzilText).filter(
            TanzilText.surah_no == surah_no,
            TanzilText.ayah_no == ayah_no,
        ).first()

        return row.text if row else ""
    finally:
        if close_db:
            db.close()


def get_surah_text(surah_no: int, start_ayah: int = None, end_ayah: int = None, db: Session = None) -> dict:
    """
    Puri surah ya ayah range ka Tanzil text return karo.

    Returns: {ayah_no: text, ...}
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        query = db.query(TanzilText).filter(TanzilText.surah_no == surah_no)

        if start_ayah is not None:
            query = query.filter(TanzilText.ayah_no >= start_ayah)
        if end_ayah is not None:
            query = query.filter(TanzilText.ayah_no <= end_ayah)

        rows = query.order_by(TanzilText.ayah_no).all()

        return {row.ayah_no: row.text for row in rows}
    finally:
        if close_db:
            db.close()