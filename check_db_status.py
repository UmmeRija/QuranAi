from database import SessionLocal, TanzilText, QuranWord, SurahInfo

db = SessionLocal()
tanzil_count = db.query(TanzilText).count()
word_count = db.query(QuranWord).count()
surah_count = db.query(SurahInfo).count()

print(f"TanzilText count: {tanzil_count}")
print(f"QuranWords count: {word_count}")
print(f"SurahInfo count: {surah_count}")

if tanzil_count > 0:
    first_ayah = db.query(TanzilText).first()
    print(f"First Ayah Sample: {first_ayah.surah_no}:{first_ayah.ayah_no} - {first_ayah.text[:50]}")

db.close()
