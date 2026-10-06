"""POST /api/council/opinion testleri (gercek LLM cagrilmaz, DB gecici dizinde).
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_council_opinion.py -q
"""
import os
import sys
import tempfile

# main import'undan ONCE: gecici DB dizini, sahte anahtarlar, admin anahtari.
_TMP = tempfile.mkdtemp(prefix="aura_council_test_")
os.environ["DB_DIR"] = _TMP
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["COUNCIL_API_KEY"] = "test-council-key"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import aura_brain  # noqa: E402
import aura_council  # noqa: E402
import aura_memory  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402

KEY = {"X-Admin-Key": "test-council-key"}
BODY = {"topic": "Hale nasil gorunmeli?", "transcript": "Gemini: sakin bir isik.", "question": "Gorusun?"}


class _Resp:
    def __init__(self, text):
        self.text = text


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    main._council_opinion_times.clear()
    monkeypatch.setattr(main, "COUNCIL_OPINION_PER_HOUR", 20)
    monkeypatch.setattr(main, "ADMIN_KEY", "test-admin-key")
    monkeypatch.setattr(main, "COUNCIL_API_KEY", "test-council-key")
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


def _total_rows():
    with database.db_cursor() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        total = 0
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            total += cur.fetchone()[0]
    return total


def test_no_key_is_404(client):
    assert client.post("/api/council/opinion", json=BODY).status_code == 404


def test_wrong_key_is_404(client):
    r = client.post("/api/council/opinion", json=BODY, headers={"X-Admin-Key": "yanlis"})
    assert r.status_code == 404


def test_council_key_unset_is_404(client, monkeypatch):
    monkeypatch.setattr(main, "COUNCIL_API_KEY", "")
    r = client.post("/api/council/opinion", json=BODY, headers={"X-Admin-Key": ""})
    assert r.status_code == 404
    r = client.post("/api/council/opinion", json=BODY, headers=KEY)
    assert r.status_code == 404


def test_admin_key_is_NOT_accepted(client, monkeypatch):
    """Konsey ucu yonetici anahtariyla ACILMAZ (en az yetki ilkesi)."""
    monkeypatch.setattr(aura_brain, "generate_with_retry", lambda *a, **k: _Resp("x"))
    r = client.post("/api/council/opinion", json=BODY, headers={"X-Admin-Key": "test-admin-key"})
    assert r.status_code == 404


def test_council_key_does_not_open_admin_endpoints(client):
    r = client.post(
        "/api/admin/set-tier",
        json={"email": "a@b.c", "tier": "pro"},
        headers={"X-Admin-Key": "test-council-key"},
    )
    assert r.status_code == 404


def test_ok_returns_reply_and_flags(client, monkeypatch):
    seen = {}

    def fake(contents, system_instruction, *a, **k):
        seen["contents"] = contents
        seen["system"] = system_instruction
        return _Resp("Bence hale sade olmali.")

    monkeypatch.setattr(aura_brain, "generate_with_retry", fake)
    r = client.post("/api/council/opinion", json=BODY, headers=KEY)
    assert r.status_code == 200
    data = r.json()
    assert data == {"reply": "Bence hale sade olmali.", "source": "aura-persona", "saved": False}
    # icerik modele gitti
    sent = seen["contents"][0].parts[0].text
    assert "Hale nasil gorunmeli?" in sent and "sakin bir isik" in sent and "Gorusun?" in sent


def test_instruction_has_character_but_no_personal_or_crisis_layer():
    ins = aura_council.build_council_instruction()
    assert aura_brain.AURA_CHARACTER_BIBLE in ins
    assert "Senin adin Aura." in ins
    assert aura_brain.KRIZ_MUDAHALE_KURALI not in ins
    assert "Kullanicinin adi" not in ins
    assert "kullanici" in ins.lower()  # "kullaniciya dair hicbir hafizan yok" notu
    assert "UYGULAMA" in ins  # prompt-injection notu


def test_nothing_is_saved_or_read_per_user(client, monkeypatch):
    """Kayit/kisiye ozel okuma fonksiyonlari cagrilirsa test patlar."""
    def boom(*a, **k):
        raise AssertionError("konsey ucu bunu CAGIRMAMALI")

    for obj, name in [
        (database, "add_message"), (database, "add_mood"),
        (database, "check_and_increment_message_usage"),
        (aura_memory, "get_memories"), (aura_memory, "get_memory_context"),
        (aura_brain, "log_distill_sample"), (aura_brain, "build_system_instruction"),
        (aura_brain, "route_request"),
    ]:
        monkeypatch.setattr(obj, name, boom)
    monkeypatch.setattr(aura_brain, "generate_with_retry", lambda *a, **k: _Resp("tamam"))

    before = _total_rows()
    r = client.post("/api/council/opinion", json=BODY, headers=KEY)
    assert r.status_code == 200
    assert _total_rows() == before


@pytest.mark.parametrize("body", [
    {"topic": ""},
    {},
    {"topic": "x" * (aura_council.MAX_TOPIC + 1)},
    {"topic": "ok", "transcript": "x" * (aura_council.MAX_TRANSCRIPT + 1)},
    {"topic": "ok", "question": "x" * (aura_council.MAX_QUESTION + 1)},
])
def test_validation_422(client, body, monkeypatch):
    monkeypatch.setattr(aura_brain, "generate_with_retry", lambda *a, **k: _Resp("x"))
    assert client.post("/api/council/opinion", json=body, headers=KEY).status_code == 422


def test_rate_limit_429(client, monkeypatch):
    monkeypatch.setattr(main, "COUNCIL_OPINION_PER_HOUR", 2)
    monkeypatch.setattr(aura_brain, "generate_with_retry", lambda *a, **k: _Resp("x"))
    codes = [client.post("/api/council/opinion", json=BODY, headers=KEY).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_generation_failure_is_502_and_does_not_leak_content(client, monkeypatch, capsys):
    def fail(*a, **k):
        raise RuntimeError("saglayici coktu: GIZLI-KONUSMA-METNI")

    monkeypatch.setattr(aura_brain, "generate_with_retry", fail)
    r = client.post("/api/council/opinion", json={"topic": "GIZLI-KONU"}, headers=KEY)
    assert r.status_code == 502
    assert r.json()["detail"] == "Aura su an cevap veremiyor."
    out = capsys.readouterr().out
    assert "GIZLI-KONU" not in out and "GIZLI-KONUSMA-METNI" not in out


def test_empty_model_reply_is_502(client, monkeypatch):
    monkeypatch.setattr(aura_brain, "generate_with_retry", lambda *a, **k: _Resp(None))
    assert client.post("/api/council/opinion", json=BODY, headers=KEY).status_code == 502
