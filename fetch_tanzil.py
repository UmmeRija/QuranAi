"""
Fetch Tanzil Text
-----------------
Tanzil.net se Uthmani Quran text download karke database mein store karo.
Is script ko ek baar chalaana kaafi hai — text permanently store ho jayega.

Usage:
    python fetch_tanzil.py
"""

from database import Base, engine, init_db
from services.tanzil_service import store_tanzil_in_db

if __name__ == "__main__":
    print("=" * 50)
    print("  Fetching Tanzil Uthmani Quran Text")
    print("=" * 50)

    # Tables create karo agar na bani hon
    init_db()

    # Download + Store
    store_tanzil_in_db()

    print("=" * 50)
    print("  Done! Tanzil reference text is ready.")
    print("=" * 50)
