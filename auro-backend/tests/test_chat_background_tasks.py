"""/api/chat'in hafiza cikarimi + pattern analizini ERTELEDIGINI, ama
hatirlatma cikarimini (reminder_result ayni turde kullanildigi icin)
ERTELEMEDIGINI dogrulayan testler (Paket 1 / madde C12).

Gercek LLM/Groq/Gemini cagrisi YAPILMAZ - generate_with_retry ve
extract_reminder_candidate stub'lanir.
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_chat_background_tasks.py -q
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="aura_chat_bg_test_")
os.environ["DB_DIR"] = _TMP
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from starlette.background import BackgroundTasks  # noqa: E402

import aura_brain  # noqa: E402
import aura_reminders  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def _make_user(email: str) -> dict:
    user = database.create_user(email, "sifre123", name="Test")
    assert user is not None
    return user


@pytest.fixture(autouse=True)
def _stub_generation(monkeypatch):
    monkeypatch.setattr(
        aura_brain, "generate_with_retry",
        lambda *a, **k: _FakeResponse("Merhaba! Nasıl yardımcı olabilirim?"),
    )
    monkeypatch.setattr(
        aura_reminders, "extract_reminder_candidate",
        lambda user_id, text: {"status": "not_found"},
    )
    yield


def test_memory_and_pattern_extraction_are_deferred_not_called_synchronously(monkeypatch):
    calls = {"memory": 0, "pattern": 0}
    monkeypatch.setattr(
        aura_brain, "extract_memory_candidate",
        lambda *a, **k: calls.__setitem__("memory", calls["memory"] + 1),
    )
    monkeypatch.setattr(
        aura_brain, "analyze_patterns",
        lambda *a, **k: calls.__setitem__("pattern", calls["pattern"] + 1),
    )

    user = _make_user("chat-bg-1@test.aura")
    bg = BackgroundTasks()
    result = main._process_chat_message(user, "merhaba, nasılsın?", bg)

    # yanit normal sekilde donmus olmali.
    assert result["reply"] == "Merhaba! Nasıl yardımcı olabilirim?"
    # ama hafiza/pattern HENUZ cagrilmamis olmali - BackgroundTasks'e
    # ERTELENMIS olmali, senkron calismamis olmali.
    assert calls["memory"] == 0
    assert calls["pattern"] == 0
    assert len(bg.tasks) == 2

    # ertelenen gorevler GERCEKTEN dogru fonksiyonlari dogru argumanlarla
    # cagiriyor mu (manuel calistirip dogruluyoruz).
    for task in bg.tasks:
        task.func(*task.args, **task.kwargs)
    assert calls["memory"] == 1
    assert calls["pattern"] == 1


def test_without_background_tasks_falls_back_to_synchronous_call(monkeypatch):
    """background_tasks=None (ornek: baska bir yerden dogrudan cagrilirsa)
    eski (senkron) davranis korunmali - hicbir yol kirilmamali."""
    calls = {"memory": 0, "pattern": 0}
    monkeypatch.setattr(
        aura_brain, "extract_memory_candidate",
        lambda *a, **k: calls.__setitem__("memory", calls["memory"] + 1),
    )
    monkeypatch.setattr(
        aura_brain, "analyze_patterns",
        lambda *a, **k: calls.__setitem__("pattern", calls["pattern"] + 1),
    )

    user = _make_user("chat-bg-2@test.aura")
    result = main._process_chat_message(user, "merhaba, nasılsın?", None)

    assert result["reply"] == "Merhaba! Nasıl yardımcı olabilirim?"
    assert calls["memory"] == 1
    assert calls["pattern"] == 1


def test_reminder_extraction_is_never_deferred(monkeypatch):
    """reminder_result AYNI turde sistem talimatina eklendigi icin
    BackgroundTasks'e ERTELENMEMELI - aksi halde Aura'nin o turde
    hatirlaticinin gercekten kurulup kurulmadigini bilmesi imkansiz hale
    gelir (2026-09-19'da duzeltilen hataya geri donus)."""
    calls = []
    monkeypatch.setattr(
        aura_reminders, "extract_reminder_candidate",
        lambda user_id, text: calls.append((user_id, text)) or {"status": "not_found"},
    )
    monkeypatch.setattr(aura_brain, "extract_memory_candidate", lambda *a, **k: None)
    monkeypatch.setattr(aura_brain, "analyze_patterns", lambda *a, **k: None)

    user = _make_user("chat-bg-3@test.aura")
    bg = BackgroundTasks()
    main._process_chat_message(user, "yarın saat 5'te doktor randevum var", bg)

    # reminder cikarimi HEMEN (senkron) cagrilmis olmali - bg.tasks
    # icinde DEGIL.
    assert len(calls) == 1
    assert all(
        task.func is not aura_reminders.extract_reminder_candidate
        for task in bg.tasks
    )
