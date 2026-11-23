"""crisis_detection testleri. Calistirma (auro-backend klasorunden):
    python -m pytest tests/test_crisis_detection.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crisis_detection import is_crisis_message  # noqa: E402


POSITIVE_CASES = [
    # --- acik ifadeler (Turkce, ASCII ve dogru yazim) ---
    "intihar etmek istiyorum",
    "kendime zarar vermek istiyorum",
    "kendimi oldurecegim",
    "kendimi öldüreceğim",
    "artik dayanamiyorum",
    "artık dayanamıyorum",
    "yaşayasım yok",
    # --- acik ifadeler (Ingilizce, duz ve akilli tirnak) ---
    "I want to kill myself",
    "I can't take it anymore",
    "I can’t take it anymore",
    # --- dolayli ifadeler (Paket 1 / madde A1) ---
    "hicbir seyin anlami yok",
    "hiçbir şeyin anlamı yok",
    "herkes bensiz daha iyi olur",
    "bugun uyuyup kalkmasam daha iyi olur",
    "everyone would be better off without me",
    "nothing matters anymore",
    # --- cok dilli ---
    "quiero morir",
    "ich will sterben",
    "хочу умереть",
]

NEGATIVE_CASES = [
    "bugün hava çok güzel",
    "harika bir gün geçirdim",
    "I am so happy today",
    "yarın toplantım var",
]
# NOT: "bu işi bitirmek istiyorum" gibi gunluk kullanimlar bilerek test
# EDILMIYOR - "bitirmek istiyorum" kelimesi (mevcut, bu PR'dan once de var
# olan bir anahtar kelime) boyle normal baglamlarda da eslesir. Bu bilinen
# ve kabul edilmis bir yanlis-pozitif (maliyeti sadece limit atlanmasi);
# dar-ve-guclu-ifade felsefesi "yanlis negatif kabul edilemez" dedigi icin
# boyle tutuluyor, bkz. crisis_detection.py modul dokstringi.


def test_positive_cases_detected():
    for text in POSITIVE_CASES:
        assert is_crisis_message(text), f"kriz ifadesi yakalanmadi: {text!r}"


def test_clearly_unrelated_cases_not_flagged():
    for text in NEGATIVE_CASES:
        assert not is_crisis_message(text), f"yanlis pozitif: {text!r}"


def test_case_insensitive_and_punctuation_tolerant():
    assert is_crisis_message("İNTİHAR etmek istiyorum.")
    assert is_crisis_message("  kendimi öldüreceğim!!  ")


def test_empty_and_unrelated_text_is_safe():
    assert is_crisis_message("") is False
    assert is_crisis_message("merhaba, nasılsın?") is False
