"""
Compare Service (Enhanced)
--------------------------
Asli Quranic text aur user ki tilawat ka lafz-ba-lafz aur character-level
muqabla karta hai.

Features:
- Complete Indo-Pak script normalization (Heh Doachashmee, Keheh, Yeh Barree, etc.)
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
SMALL_SIGNS_RE = re.compile(r'[\u06D6-\u06ED\u0615-\u061A\u200C\u200D\u200F]')

TATWEEL = '\u0640'

# ── Complete Indo-Pak → Standard Arabic Mapping ─────────────────────────────
# Tanzil IndoPak script ke saare special characters yahan hain
INDOPAK_MAP = [
    # Heh variants (sabse common missing issue — Surah Fatiha mein ھ)
    ('\u06BE', '\u0647'),  # ھ  Heh Doachashmee     → ه Haa
    ('\u06C1', '\u0647'),  # ہ  Heh Goal             → ه Haa
    ('\u06C3', '\u0647'),  # ۃ  Teh Marbuta Goal     → ه Haa

    # Kaf variants
    ('\u06A9', '\u0643'),  # ک  Keheh (Indo-Pak Kaf) → ك Kaf
    ('\u06AA', '\u0643'),  # ڪ  Swash Kaf            → ك Kaf

    # Yeh/Alif variants
    ('\u06D2', '\u064A'),  # ے  Yeh Barree           → ي Ya
    ('\u06CC', '\u064A'),  # ی  Farsi Yeh            → ي Ya
    ('\u0649', '\u064A'),  # ى  Alif Maqsura         → ي Ya
    ('\u06CD', '\u064A'),  # ۍ  Yeh With Tail        → ي Ya

    # Hamza variants → plain Alif
    ('\u0623', '\u0627'),  # أ  Alif With Hamza Above → ا Alif
    ('\u0625', '\u0627'),  # إ  Alif With Hamza Below → ا Alif
    ('\u0622', '\u0627'),  # آ  Alif With Madda       → ا Alif
    ('\u0671', '\u0627'),  # ٱ  Alif Wasla            → ا Alif
    ('\u0672', '\u0627'),  # ٲ  Alif With Wavy Hamza → ا Alif
    ('\u0673', '\u0627'),  # ٳ  Alif With Subscript  → ا Alif

    # Waw/Hamza
    ('\u0624', '\u0648'),  # ؤ  Waw With Hamza       → و Waw

    # Ya With Hamza
    ('\u0626', '\u064A'),  # ئ  Ya With Hamza        → ي Ya

    # Taa Marbuta → Haa (loose matching)
    ('\u0629', '\u0647'),  # ة  Taa Marbuta          → ه Haa

    # Noon Ghunna
    ('\u06BA', '\u0646'),  # ں  Noon Ghunna          → ن Noon

    # Rreh (Urdu Ra)
    ('\u0691', '\u0631'),  # ڑ  Rreh                 → ر Ra
]


def _normalize_arabic(text: str, strip_harakat: bool = True) -> str:
    """
    Arabic/Indo-Pak text ko normalize karo comparison ke liye.

    Steps:
    1. Unicode NFKC normalization
    2. Harakat/diacritics strip (conditional)
    3. Small Quranic signs remove
    4. Indo-Pak → Standard Arabic character mapping
    5. Tatweel remove
    6. Punctuation remove
    7. Whitespace cleanup
    """
    if not text:
        return ""

    # Step 1: Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Step 2: Remove ALL diacritics/harakat (Unicode category Mn = Mark, Nonspacing)
    if strip_harakat:
        text = "".join(c for c in text if unicodedata.category(c) != 'Mn')

    # Step 3: Remove small Quranic signs and zero-width chars
    text = SMALL_SIGNS_RE.sub('', text)

    # Step 4: Indo-Pak → Standard Arabic mapping (order matters!)
    for indo, arabic in INDOPAK_MAP:
        text = text.replace(indo, arabic)

    # Step 5: Remove Tatweel/Kashida
    text = text.replace(TATWEEL, '')

    # Step 6: Remove punctuation (Arabic + Urdu + Latin)
    text = re.sub(r'[.,!?;:۔،؟؛…»«\u06D4\u061B\u061F]', '', text)

    # Step 7: Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def _word_similarity(word1: str, word2: str) -> float:
    """
    Do Arabic words ke beech similarity ratio (0.0 to 1.0).
    """
    norm1 = _normalize_arabic(word1)
    norm2 = _normalize_arabic(word2)

    if not norm1 and not norm2:
        return 1.0
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0

    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


# ── Fuzzy match threshold ────────────────────────────────────────────────────
FUZZY_THRESHOLD = 0.65


def compare_words(
    correct_words: List[str],
    recited_words: List[str],
    intro_word_count: int = 0,
) -> tuple[List[WordAnalysis], float]:
    """
    Correct aur recited words ka muqabla karo.

    Args:
        correct_words: Database se mile actual Quranic words
        recited_words: ASR se mili user ki tilawat ke words
        intro_word_count: Pehle kitne alfaaz Intro (Ta'awwudh/Bismillah) ke hain?

    Returns:
        (word_analysis list, accuracy percentage)
    """
    if not correct_words:
        return [], 0.0

    # Normalize karo comparison ke liye
    correct_norm = [_normalize_arabic(w) for w in correct_words]
    recited_norm = [_normalize_arabic(w) for w in recited_words]

    # Debug log — is se pata chalega normalization kaam kar raha hai ya nahi
    print(f"[Compare] Correct words (normalized): {correct_norm[:5]}...")
    print(f"[Compare] Recited words (normalized): {recited_norm[:5]}...")

    # Alignment: check if user skipped Bismillah/intro
    if intro_word_count > 0 and len(recited_norm) > 0 and len(correct_norm) > intro_word_count:
        sim_with_intro_start = _word_similarity(correct_norm[0], recited_norm[0])
        sim_with_surah_start = _word_similarity(correct_norm[intro_word_count], recited_norm[0])

        if sim_with_surah_start > sim_with_intro_start and sim_with_surah_start > FUZZY_THRESHOLD:
            print(f"[Compare] User likely skipped intro ({intro_word_count} words).")

    matcher = difflib.SequenceMatcher(None, correct_norm, recited_norm, autojunk=False)
    opcodes = matcher.get_opcodes()

    word_analysis: List[WordAnalysis] = []
    correct_count = 0
    actual_target_count = len(correct_words) - intro_word_count

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for idx, ci in enumerate(range(i1, i2)):
                ji = j1 + idx
                word_analysis.append(WordAnalysis(
                    correct_word=correct_words[ci],
                    user_word=recited_words[ji] if ji < len(recited_words) else None,
                    status="match",
                    position=ci + 1,
                ))
            correct_count += (i2 - i1)

        elif tag == "replace":
            for idx, ci in enumerate(range(i1, i2)):
                ji = j1 + idx
                if ji < j2 and ji < len(recited_words):
                    similarity = _word_similarity(correct_words[ci], recited_words[ji])
                    if similarity >= FUZZY_THRESHOLD:
                        word_analysis.append(WordAnalysis(
                            correct_word=correct_words[ci],
                            user_word=recited_words[ji],
                            status="match",
                            position=ci + 1,
                        ))
                        correct_count += 1
                    else:
                        word_analysis.append(WordAnalysis(
                            correct_word=correct_words[ci],
                            user_word=recited_words[ji],
                            status="incorrect",
                            position=ci + 1,
                        ))
                else:
                    word_analysis.append(WordAnalysis(
                        correct_word=correct_words[ci],
                        user_word=None,
                        status="missing",
                        position=ci + 1,
                    ))

        elif tag == "delete":
            for ci in range(i1, i2):
                word_analysis.append(WordAnalysis(
                    correct_word=correct_words[ci],
                    user_word=None,
                    status="missing",
                    position=ci + 1,
                ))

        elif tag == "insert":
            # Extra words jo user ne parhe lekin correct text mein nahi — ignore
            pass

    word_analysis.sort(key=lambda x: x.position)

    # Accuracy sirf main words par (intro exclude)
    correct_intro = sum(
        1 for w in word_analysis
        if w.status == "match" and w.position <= intro_word_count
    )
    correct_main = correct_count - correct_intro

    accuracy = round((correct_main / actual_target_count) * 100, 2) if actual_target_count > 0 else 0.0
    accuracy = max(0.0, min(100.0, accuracy))

    print(f"[Compare] Correct main: {correct_main}/{actual_target_count} = {accuracy}%")
    return word_analysis, accuracy


def compare_ayah_text(
    reference_text: str,
    transcribed_text: str,
) -> dict:
    """
    Ayah level pe word-level comparison (Tanzil reference vs transcribed).

    Returns:
        dict: {accuracy, correct_words, total_words, missing_words, incorrect_words}
    """
    ref_norm = _normalize_arabic(reference_text)
    trans_norm = _normalize_arabic(transcribed_text)

    ref_words = ref_norm.split()
    trans_words = trans_norm.split()

    if not ref_words:
        return {
            "accuracy": 0.0,
            "correct_words": 0,
            "total_words": 0,
            "missing_words": [],
            "incorrect_words": [],
        }

    matcher = difflib.SequenceMatcher(None, ref_words, trans_words, autojunk=False)
    opcodes = matcher.get_opcodes()

    correct_count = 0
    missing_words = []
    incorrect_words = []

    # Keep original (with tashkeel) words for reporting
    original_ref_words = reference_text.split()

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            correct_count += (i2 - i1)
        elif tag == "replace":
            for idx, ci in enumerate(range(i1, i2)):
                ji = j1 + idx
                orig_word = original_ref_words[ci] if ci < len(original_ref_words) else ref_words[ci]
                if ji < j2 and ji < len(trans_words):
                    sim = _word_similarity(ref_words[ci], trans_words[ji])
                    if sim >= FUZZY_THRESHOLD:
                        correct_count += 1
                    else:
                        incorrect_words.append(orig_word)
                else:
                    missing_words.append(orig_word)
        elif tag == "delete":
            for ci in range(i1, i2):
                orig_word = original_ref_words[ci] if ci < len(original_ref_words) else ref_words[ci]
                missing_words.append(orig_word)

    total = len(ref_words)
    accuracy = round((correct_count / total) * 100, 2) if total > 0 else 0.0

    return {
        "accuracy": accuracy,
        "correct_words": correct_count,
        "total_words": total,
        "missing_words": missing_words,
        "incorrect_words": incorrect_words,
    }