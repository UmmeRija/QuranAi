import requests
import time
from database import SessionLocal, Base, engine, QuranWord

# Database tables create karna
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Ta'awwudh aur Tasmiyah ke lafz (Uthmani Script)
audhu_words = ["أَعُوذُ", "بِاللَّهِ", "مِنَ", "الشَّيْطَانِ", "الرَّجِيمِ"]
bismillah_words = ["بِسْمِ", "اللَّهِ", "الرَّحْمَٰنِ", "الرَّحِيمِ"]

print("Starting to fetch data from Quran.com API with Ta'awwudh and Bismillah...")

# Last 10 Surahs (105 to 114)
for surah in range(105, 115):
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
                    words = verse.get("words", [])
                    
                    for word in words:
                        if word.get("char_type_name") == "word":
                            # API se lafz nikal kar DB mein daalna
                            new_word = QuranWord(
                                surah_no=surah,
                                ayah_no=ayah_no,
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
print("\nCongratulations! Database with Ta'awwudh and Bismillah is ready for Surahs 105-114.")