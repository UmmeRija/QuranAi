import requests
import time
from database import SessionLocal, Base, engine, QuranWord, SurahInfo

# Database tables create karna
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Ta'awwudh aur Tasmiyah ke lafz (Uthmani Script)
audhu_words = ["أَعُوذُ", "بِاللَّهِ", "مِنَ", "الشَّيْطَانِ", "الرَّجِيمِ"]
bismillah_words = ["بِسْمِ", "اللَّهِ", "الرَّحْمَٰنِ", "الرَّحِيمِ"]

print("Starting to fetch data from Quran.com API with Ta'awwudh and Bismillah...")

print("Cleaning up existing records for all Surahs (1-114)...")
db.query(QuranWord).delete()
db.query(SurahInfo).delete()
db.commit()
print("Cleanup done. Starting full Quran fetch...")

# ── Step 1: Fetch Surah Info (Metadata) ──────────────────────────────────────
print("Fetching Surah Metadata (Names and Verse counts)...")
chapters_url = "https://api.quran.com/api/v4/chapters?language=en"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

try:
    resp = requests.get(chapters_url, headers=headers)
    if resp.status_code == 200:
        chapters = resp.json().get("chapters", [])
        for ch in chapters:
            surah_no = ch["id"]
            # Urdu names are not easily available in one call, so we'll use a simple fallback
            # or you can add another call for urdu language.
            new_surah = SurahInfo(
                surah_no=surah_no,
                name_arabic=ch["name_arabic"],
                name_english=ch["translated_name"]["name"],
                name_urdu=ch["name_simple"], # Fallback for now
                total_verses=ch["verses_count"]
            )
            db.add(new_surah)
        db.commit()
        print(f"Successfully saved info for {len(chapters)} Surahs.")
except Exception as e:
    print(f"Error fetching metadata: {e}")

# ── Step 2: Fetch Word-by-Word Data ──────────────────────────────────────────
# Last 114 Surahs (1 to 114)
for surah in range(1, 115):
    print(f"--- Processing Surah {surah} ---")
    
    # 1. Manual Insertion: A'udhu Billah aur Bismillah add karna
    current_pos = 1
    
    # A'udhu Billah add ho raha hai
    for word in audhu_words:
        db.add(QuranWord(
            surah_no=surah,
            ayah_no=0, # Intro words ke liye Ayah 0 rakha hai
            word_arabic=word,
            word_position=current_pos
        ))
        current_pos += 1
        
    # Bismillah add ho rahi hai
    for word in bismillah_words:
        db.add(QuranWord(
            surah_no=surah,
            ayah_no=0,
            word_arabic=word,
            word_position=current_pos
        ))
        current_pos += 1
    
    # 2. API Fetching: Surah ki Ayaat nikalna
    url = f"https://api.quran.com/api/v4/verses/by_chapter/{surah}?words=true&word_fields=text_uthmani"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                verses = data.get("verses", [])
                
                for verse in verses:
                    ayah_no = verse["verse_number"]
                    ruku_no = verse.get("ruku_number") or 0
                    words = verse.get("words", [])
                    
                    for word in words:
                        if word.get("char_type_name") == "word":
                            # API se lafz nikal kar DB mein daalna
                            new_word = QuranWord(
                                surah_no=surah,
                                ayah_no=ayah_no,
                                ruku_no=ruku_no,
                                page_no=word.get("page_number"),
                                line_no=word.get("line_number"),
                                word_arabic=word.get("text_uthmani") or word.get("text"),
                                word_position=word.get("position")
                            )
                            db.add(new_word)
                
                db.commit() # Surah ka sara data save ho gaya
                print(f"Surah {surah} (including Intro) successfully saved!")
                break 
                
            else:
                print(f"Failed to fetch Surah {surah}. Status Code: {response.status_code}")
                break
                
        except requests.exceptions.ConnectionError:
            print(f"Connection lost on Surah {surah}. Retrying... ({attempt + 1}/{max_retries})")
            time.sleep(3)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break
            
    # API server par bojh na dalne ke liye chota sa pause
    time.sleep(1.5)

db.close()
print("\nCongratulations! Database with Ta'awwudh and Bismillah is ready for Surahs 57-114.")