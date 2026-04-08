"""
Compare Service
---------------
Asli Quranic text aur user ki tilawat ka lafz-ba-lafz muqabla karta hai.
Har lafz ka status return karta hai: "correct", "incorrect", ya "missing".
"""

import difflib
import unicodedata
from typing import List
from models.schemas import WordAnalysis


def _normalize(word: str) -> str:
    """
    Arabic harakat (diacritics) hatao comparison ke liye.
    Maslan: 'بِسْمِ' aur 'بسم' dono same manay jayenge.
    """
    # Unicode normalization
    word = unicodedata.normalize("NFKC", word)
    # Arabic diacritics (harakat) Unicode range: U+064B to U+065F
    return "".join(ch for ch in word if not ("\u064b" <= ch <= "\u065f"))


def compare_words(
    correct_words: List[str],
    recited_words: List[str],
) -> tuple[List[WordAnalysis], float]:
    """
    Correct aur recited words ka muqabla karo.

    Args:
        correct_words: Database se mile actual Quranic words
        recited_words: Whisper se mili user ki tilawat ke words

    Returns:
        (word_analysis_list, accuracy_percentage)
    """
    # Normalize both lists for comparison
    correct_norm = [_normalize(w) for w in correct_words]
    recited_norm = [_normalize(w) for w in recited_words]

    # difflib se sequence matcher
    matcher = difflib.SequenceMatcher(None, correct_norm, recited_norm)
    opcodes = matcher.get_opcodes()

    word_analysis: List[WordAnalysis] = []
    correct_count = 0

    # opcodes: ('equal'/'replace'/'delete'/'insert', i1, i2, j1, j2)
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            # Bilkul sahi parhay gaye
            for idx, ci in enumerate(range(i1, i2)):
                word_analysis.append(
                    WordAnalysis(
                        word=correct_words[ci],
                        status="correct",
                        position=ci + 1,
                    )
                )
            correct_count += (i2 - i1)

        elif tag == "replace":
            # Galat parhay gaye (correct ki jagah kuch aur bola)
            for ci in range(i1, i2):
                word_analysis.append(
                    WordAnalysis(
                        word=correct_words[ci],
                        status="incorrect",
                        position=ci + 1,
                    )
                )

        elif tag == "delete":
            # Correct text mein hai lekin user ne nahi parha (missing)
            for ci in range(i1, i2):
                word_analysis.append(
                    WordAnalysis(
                        word=correct_words[ci],
                        status="missing",
                        position=ci + 1,
                    )
                )

        # "insert" = user ne extra bola — hum ignore karte hain
        # (correct list mein nahi tha toh penalize nahi)

    # Position ke hisaab se sort karo
    word_analysis.sort(key=lambda x: x.position)

    # Accuracy calculate karo
    total = len(correct_words)
    accuracy = round((correct_count / total) * 100, 2) if total > 0 else 0.0

    return word_analysis, accuracy
