import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'python', 'data', 'quran.db')

def verify_population():
    print("-" * 30)
    print("Quran Database Verification")
    print("-" * 30)
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Total Counts
        cursor.execute("SELECT COUNT(*) FROM surah_info")
        total_surahs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM quran_words")
        total_words = cursor.fetchone()[0]

        print(f"Total Surahs: {total_surahs}")
        print(f"Total Words:  {total_words}")
        print("-" * 30)

        # 2. Check specific Surahs
        check_ids = [1, 2, 36, 67, 114]
        print(f"{'Surah':<10} | {'Ayahs Found':<12} | {'Complete?'}")
        print("-" * 30)
        
        for sid in check_ids:
            # Metadata count
            cursor.execute("SELECT total_verses FROM surah_info WHERE surah_no = ?", (sid,))
            meta_resp = cursor.fetchone()
            if not meta_resp:
                continue
            meta_count = meta_resp[0]
            
            # Words count (Ayah 0 is intro, so we subtract it if we only want verse count)
            cursor.execute("SELECT COUNT(DISTINCT ayah_no) FROM quran_words WHERE surah_no = ?", (sid,))
            actual_ayahs_with_intro = cursor.fetchone()[0]
            actual_verses = actual_ayahs_with_intro - 1 # Subtract Ayah 0
            
            status = " [DONE]" if actual_verses >= meta_count else f" [INCOMPLETE] ({actual_verses}/{meta_count})"
            print(f"{sid:<10} | {actual_verses:<12} | {status}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_population()
