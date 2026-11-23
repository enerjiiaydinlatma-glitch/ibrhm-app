"""aura_voice.py kriz guvenlik agi testleri (gercek WebSocket/Gemini Live
baglantisi KURULMAZ - sadece baglanti ONCESI kontrol ve saf mantik
fonksiyonlari test edilir).
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_aura_voice_crisis.py -q
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="aura_voice_crisis_test_")
os.environ["DB_DIR"] = _TMP
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aura_voice  # noqa: E402
import database  # noqa: E402

database.init_db()


def _make_user(email: str) -> dict:
    user = database.create_user(email, "sifre123", name="Test")
    assert user is not None
    return user


def test_recent_text_was_crisis_true_when_last_message_is_crisis():
    user = _make_user("kriz-voice-1@test.aura")
    database.add_message(user["id"], "user", "artık dayanamıyorum")
    assert aura_voice._recent_text_was_crisis(user["id"]) is True


def test_recent_text_was_crisis_false_for_ordinary_message():
    user = _make_user("kriz-voice-2@test.aura")
    database.add_message(user["id"], "user", "bugün hava çok güzel")
    assert aura_voice._recent_text_was_crisis(user["id"]) is False


def test_recent_text_was_crisis_false_when_no_messages():
    user = _make_user("kriz-voice-3@test.aura")
    assert aura_voice._recent_text_was_crisis(user["id"]) is False


def test_recent_text_was_crisis_only_looks_at_last_user_message():
    user = _make_user("kriz-voice-4@test.aura")
    database.add_message(user["id"], "user", "artık dayanamıyorum")
    database.add_message(user["id"], "assistant", "Yanındayım, güvende misin?")
    database.add_message(user["id"], "user", "sakinleştim, iyiyim şimdi")
    # en son kullanici mesaji kriz ifadesi degil -> sinir gevsetilmemeli
    assert aura_voice._recent_text_was_crisis(user["id"]) is False


def test_crisis_voice_grace_seconds_is_a_positive_bounded_value():
    # sinirsiz degil (maliyet kontrolu), ama makul bir pay (dakika > 0).
    assert 0 < aura_voice.CRISIS_VOICE_GRACE_SECONDS <= 3600
