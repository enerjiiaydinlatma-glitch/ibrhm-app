"""mood_detection testleri. Calistirma (auro-backend klasorunden):
    python -m pytest tests/test_mood_detection.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mood_detection import detect_mood, detect_moods  # noqa: E402


# (mesaj, beklenen moods listesi)
CASES = [
    # --- temel eslesme (eski davranis korunur) ---
    ("Bugun cok mutluyum", ["mutlu"]),
    ("Ne harika bir gun", ["mutlu"]),
    ("Çok keyifli bir akşamdı", ["mutlu"]),
    ("Canım sıkkın bugün", ["uzgun"]),
    ("Moralim bozuk", ["uzgun"]),
    ("Çok üzgünüm", ["uzgun"]),
    ("Bugün berbat geçti", ["uzgun"]),
    ("Çok yorgunum", ["yorgun"]),
    ("Halsizim, uykum var", ["yorgun"]),
    ("Çok stresliyim", ["stresli"]),
    ("Endişeliyim yarın için", ["stresli"]),
    ("Bugün çok enerjik hissediyorum", ["enerjik"]),
    ("Heyecanlıyım!", ["enerjik"]),  # ı->i katlamasiyla "heyecanliyim" eslesir
    ("I'm so happy today", ["mutlu"]),
    ("Feeling really tired", ["yorgun"]),
    ("I feel anxious", ["stresli"]),
    ("So excited for tomorrow", ["enerjik"]),
    # --- sonek alan Turkce kelimeler ---
    ("mutluyum", ["mutlu"]),
    ("yorgunlukla bas edemiyorum", ["yorgun"]),
    # --- alakasiz mesaj ---
    ("Bugün hava nasıl olacak?", []),
    ("Bana bir tarif öner", []),
    ("", []),
    # --- TAM KELIME hatasi: "sadece" artik uzgun degil ---
    ("Sadece bir soru sormak istiyorum", []),
    ("Sade bir kahve içtim", []),
    ("Sadık dostum geldi", []),
    ("Download the file", []),
    ("Superman filmi izledim", []),
    ("I am a bit saddled with work", []),
    # --- OLUMSUZLAMA (Turkce, kelimeden SONRA) ---
    ("Yorgun değilim", []),
    ("yorgun degilim", []),
    ("Hiç mutlu değilim", []),
    ("Mutlu degildim", []),
    ("Stresli değil", []),
    # --- OLUMSUZLAMA (Ingilizce, kelimeden ONCE) ---
    ("I'm not happy", []),
    ("I am not tired at all", []),
    ("I don't feel sad", []),
    ("I'm no longer anxious", []),
    ("It isn't great", []),
    ("never happy", []),
    # --- olumsuzlama cumle siniri: baska cumleye tasmaz ---
    ("Değil mi? Yorgunum", ["yorgun"]),
    ("Not now. I'm tired", ["yorgun"]),
    # --- COKLU DUYGU: mesajdaki sirayla ---
    ("Yorgunum ama harika bir gün", ["yorgun", "mutlu"]),
    ("Harika bir gün ama yorgunum", ["mutlu", "yorgun"]),
    ("I'm tired but excited", ["yorgun", "enerjik"]),
    ("Çok stresliyim ve üzgünüm", ["stresli", "uzgun"]),
    ("Mutluyum, mutluyum, çok mutluyum", ["mutlu"]),  # tekrar tek sayilir
    # --- bir duygu olumsuz, digeri degil ---
    ("Yorgun değilim ama stresliyim", ["stresli"]),
    ("I'm not sad, just tired", ["yorgun"]),
    # --- Turkce karakter varyantlari ---
    ("SÜPER bir gün", ["mutlu"]),
    ("Süper!", ["mutlu"]),
    ("ENDİŞELİYİM", ["stresli"]),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_detect_moods(text, expected):
    assert detect_moods(text) == expected


def test_detect_mood_backwards_compatible():
    assert detect_mood("Yorgunum ama harika") == "yorgun"
    assert detect_mood("Sadece soru") is None
    assert detect_mood("yorgun degilim") is None


def test_crisis_keywords_not_touched():
    """Kriz tespiti bu modulun DISINDA kalmali: modulde kriz kelimesi yok."""
    import mood_detection
    src = open(mood_detection.__file__, encoding="utf-8").read().lower()
    for kw in ("intihar", "kendime zarar", "oldur"):
        assert kw not in src
