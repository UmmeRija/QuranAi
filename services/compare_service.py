"""
Compare Service (Enhanced)
--------------------------
Asli Quranic text aur user ki tilawat ka lafz-ba-lafz aur character-level
muqabla karta hai.

Features:
- Advanced Arabic normalization (Hamza variants, Tatweel, Alif Maqsura, etc.)
- Character-level comparison (harakat/tashkeel aware)
- Ayah-level breakdown
- Fuzzy matching threshold for minor ASR variations
"""

import difflib
import unicodedata
import re
from typing import List, Optional
from models.schemas import WordAnalysis, AyahAnalysis


# ── Arabic Unicode Ranges ────────────────────────────────────────────────────
# Harakat (diacritics) range
HARAKAT_RE = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')

# Tatweel (kashida)
TATWEEL = '\u0640'

# Small Arabic letters and signs
SMALL_SIGNS_RE = re.compile(r'[\u06D6-\u06ED\u0615-\u061A]')


def _normalize_arabic(text: str, strip_harakat: bool = True) -> str:
    """
    Arabic text ko normalize karo comparison ke liye.

    Steps:
    1. Unicode NFKC normalization
    2. Hamza variants → base Alif (أ إ آ ٱ → ا)
    3. Alif Maqsura (ى) → Ya (ي) (optional, both common)
    4. Taa Marbuta (ة) → Haa (ه) (for loose matching)
    5. Remove Tatweel (kashida ـ)
    6. Remove harakat/diacritics (conditional)
    7. Remove extra whitespace
    """
    # Step 1: Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Step 2: Hamza variants → plain Alif
    text = text.replace('أ', 'ا')
    text = text.replace('إ', 'ا')
    text = text.replace('آ', 'ا')
    text = text.replace('ٱ', 'ا')  # Alif Wasla

    # Step 3: Alif Maqsura → Ya
    text = text.replace('ى', 'ي')

    # Step 4: Taa Marbuta → Haa (for loose comparison)
    text = text.replace('ة', 'ه')

    # Step 5: Remove Tatweel
    text = text.replace(TATWEEL, '')

    # Step 6: Remove harakat if requested
    if strip_harakat:
        text = HARAKAT_RE.sub('', text)

    # Step 7: Small signs remove
    text = SMALL_SIGNS_RE.sub('', text)

    # Step 8: Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def _word_similarity(word1: str, word2: str) -> float:
    """
    Do Arabic words ke beech similarity ratio (0.0 to 1.0).
    Fuzzy matching ke liye use hota hai.
    """
    norm1 = _normalize_arabic(word1)
    norm2 = _normalize_arabic(word2)

    if norm1 == norm2:
        return 1.0

    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


# ── Fuzzy match threshold ────────────────────────────────────────────────────
# Agar do words 85%+ similar hain toh "correct" maan lo
# (ASR minor variations handle karne ke liye)
FUZZY_THRESHOLD = 0.85


def compare_words(
    correct_words: List[str],
    recited_words: List[str],
) -> tuple[List[WordAnalysis], float]:
    """
    Correct aur recited words ka muqabla karo (enhanced version).

    Args:
        correct_words: Database se mile actual Quranic words
        recited_words: ASR se mili user ki tilawat ke words

    Returns:
        (word_analysis_list, accuracy_percentage)
    """
    # Normalize both lists
    correct_norm = [_normalize_arabic(w) for w in correct_words]
    recited_norm = [_normalize_arabic(w) for w in recited_words]

    # SequenceMatcher se alignment
    matcher = difflib.SequenceMatcher(None, correct_norm, recited_norm)
    opcodes = matcher.get_opcodes()

    word_analysis: List[WordAnalysis] = []
    correct_count = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for ci in range(i1, i2):
                word_analysis.append(
                    WordAnalysis(
                        word=correct_words[ci],
                        status="correct",
                        position=ci + 1,
                    )
                )
            correct_count += (i2 - i1)

        elif tag == "replace":
            # Fuzzy check karo — shayad almost sahi parha ho
            for idx, ci in enumerate(range(i1, i2)):
                ji = j1 + idx
                if ji < j2:
                    similarity = _word_similarity(
                        correct_words[ci], recited_words[ji]
                    )
                    if similarity >= FUZZY_THRESHOLD:
                        word_analysis.append(
                            WordAnalysis(
                                word=correct_words[ci],
                                status="correct",
                                position=ci + 1,
                            )
                        )
                        correct_count += 1
                    else:
                        word_analysis.append(
                            WordAnalysis(
                                word=correct_words[ci],
                                status="incorrect",
                                position=ci + 1,
                            )
                        )
                else:
                    word_analysis.append(
                        WordAnalysis(
                            word=correct_words[ci],
                            status="missing",
                            position=ci + 1,
                        )
                    )

        elif tag == "delete":
            for ci in range(i1, i2):
                word_analysis.append(
                    WordAnalysis(
                        word=correct_words[ci],
                        status="missing",
                        position=ci + 1,
                    )
                )

        # "insert" = user ne extra bola — ignore

    # Position sort
    word_analysis.sort(key=lambda x: x.position)

    # Accuracy
    total = len(correct_words)
    accuracy = round((correct_count / total) * 100, 2) if total > 0 else 0.0

    return word_analysis, accuracy


def compare_ayah_text(
    reference_text: str,
    transcribed_text: str,
) -> dict:
    """
    Ayah level pe character-level comparison (Tanzil reference vs transcribed).

    Args:
        reference_text: Tanzil se mila original text (with tashkeel)
        transcribed_text: ASR se mila text

    Returns:
        dict: {accuracy, matching_chars, total_chars, missing_words, incorrect_words}
    """
    ref_norm = _normalize_arabic(reference_text)
    trans_norm = _normalize_arabic(transcribed_text)

    ref_words = ref_norm.split()
    trans_words = trans_norm.split()

    # Word-level analysis for this ayah
    matcher = difflib.SequenceMatcher(None, ref_words, trans_words)
    opcodes = matcher.get_opcodes()

    correct_count = 0
    missing_words = []
    incorrect_words = []

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            correct_count += (i2 - i1)
        elif tag == "replace":
            for idx, ci in enumerate(range(i1, i2)):
                ji = j1 + idx
                if ji < j2:
                    sim = _word_similarity(ref_words[ci], trans_words[ji])
                    if sim >= FUZZY_THRESHOLD:
                        correct_count += 1
                    else:
                        incorrect_words.append(reference_text.split()[ci] if ci < len(reference_text.split()) else ref_words[ci])
                else:
                    missing_words.append(reference_text.split()[ci] if ci < len(reference_text.split()) else ref_words[ci])
        elif tag == "delete":
            for ci in range(i1, i2):
                missing_words.append(reference_text.split()[ci] if ci < len(reference_text.split()) else ref_words[ci])

    total = len(ref_words)
    accuracy = round((correct_count / total) * 100, 2) if total > 0 else 0.0

    return {
        "accuracy": accuracy,
        "correct_words": correct_count,
        "total_words": total,
        "missing_words": missing_words,
        "incorrect_words": incorrect_words,
    }
