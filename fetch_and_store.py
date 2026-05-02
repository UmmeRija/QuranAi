import requests
import time
import os
from database import SessionLocal, Base, engine, QuranWord, SurahInfo, TanzilText
from services.tanzil_service import store_tanzil_in_db, get_surah_text

# Database setup
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Ta'awwudh aur Tasmiyah ke lafz (IndoPak Style matching text)
# Note: In IndoPak script, spelling might be slightly different.
# We'll stick to a verified standard for these as well.
audhu_words = ["أَعُوذُ", "بِاللَّهِ", "مِنَ", "الشَّيْطَانِ", "الرَّجِيمِ"]
bismillah_words = ["بِسْمِ", "اللَّهِ", "الرَّحْمَٰنِ", "الرَّحِيمِ"]

print("="*60)
print("  Quran Database Population — Authentic Tanzil IndoPak Edition")
print("="*60)

# ── Step 1: Initialize Tanzil Reference Text ────────────────────────────────
print("\n[Step 1] Initializing Tanzil IndoPak reference text...")
try:
    # Ensure current Tanzil data is clean for the new script
    db.query(TanzilText).delete()
    db.commit()
    store_tanzil_in_db(db)
    print("  Tanzil IndoPak text ready.")
except Exception as e:
    print(f"  Error initializing Tanzil: {e}")

# ── Step 2: Fetch Surah Metadata ──────────────────────────────────────────
print("\n[Step 2] Fetching Surah Metadata...")
chapters_url = "https://api.quran.com/api/v4/chapters?language=en"
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    resp = requests.get(chapters_url, headers=headers)
    if resp.status_code == 200:
        chapters = resp.json().get("chapters", [])
        for ch in chapters:
            surah_no = ch["id"]
            existing = db.query(SurahInfo).filter(SurahInfo.surah_no == surah_no).first()
            if not existing:
                db.add(SurahInfo(
                    surah_no=surah_no,
                    name_arabic=ch["name_arabic"],
                    name_english=ch["name_simple"],
                    name_urdu=ch["name_simple"],
                    total_verses=ch["verses_count"]
                ))
            else:
                existing.total_verses = ch["verses_count"]
        db.commit()
        print(f"  Metadata for {len(chapters)} Surahs ready.")
except Exception as e:
    print(f"  Metadata error: {e}")

# ── Step 3: Populate Words directly from Tanzil IndoPak ───────────────────
print("\n[Step 3] Populating Word-by-Word data from Tanzil (Authentic)...")

# Optional: Cleanup whole table for fresh start if needed
# db.query(QuranWord).delete()
# db.commit()

for surah_no in range(1, 115):
    # Fetch Tanzil ayahs for this surah
    ayah_texts = get_surah_text(surah_no, db=db)
    if not ayah_texts:
        print(f"  Skipping Surah {surah_no}: No Tanzil text found.")
        continue
    
    # Cleanup only this surah
    db.query(QuranWord).filter(QuranWord.surah_no == surah_no).delete()
    db.commit()

    # 1. Intro Words (Ayah 0)
    current_pos = 1
    # Adding Ta'awwudh
    for w in audhu_words:
        db.add(QuranWord(surah_no=surah_no, ayah_no=0, word_arabic=w, word_position=current_pos))
        current_pos += 1
    # Adding Bismillah (Except for Surah 9, though usually people say it anyway, 
    # but for Tanzil consistency we keep Intro logic same)
    for w in bismillah_words:
        db.add(QuranWord(surah_no=surah_no, ayah_no=0, word_arabic=w, word_position=current_pos))
        current_pos += 1

    # 2. Main Ayahs from Tanzil
    for ayah_no, text in ayah_texts.items():
        # Split Ayah text into words accurately
        # Note: Arabic splitting can be tricky with specific hamzas, but simple split works for most scripts
        words = text.split()
        for idx, w in enumerate(words):
            db.add(QuranWord(
                surah_no=surah_no,
                ayah_no=ayah_no,
                word_arabic=w,
                word_position=idx + 1
            ))
    
    db.commit()
    print(f"  Surah {surah_no:3} | {len(ayah_texts):3} Ayahs | Done")

db.close()
print("\n" + "="*60)
print("  SUCCESS: Full Quran populated with Authentic IndoPak text.")
print("="*60)