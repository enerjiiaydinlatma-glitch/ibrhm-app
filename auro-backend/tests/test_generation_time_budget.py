"""generate_with_retry toplam zaman butcesi testleri (Paket 1 / madde C12:
Gemini + Groq/Cerebras/Mistral/OpenRouter zincirinin TOPLAMDA sinirsiz
surebilmesi riski - artik TOTAL_GENERATION_BUDGET_SECONDS ile sinirli).
Hicbir gercek aga cikan cagri YAPILMAZ - tum saglayicilar sahte/yavas
fonksiyonlarla degistirilir.
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_generation_time_budget.py -q
"""
import os
import sys
import tempfile

os.environ["DB_DIR"] = tempfile.mkdtemp(prefix="aura_budget_test_")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

import aura_brain  # noqa: E402


class _Boom(Exception):
    pass


def _always_fails(*_a, **_k):
    raise _Boom("saglayici her zaman basarisiz (test)")


def test_fallback_chain_stops_once_budget_is_exhausted(monkeypatch):
    # Birincil (Gemini) saglayici hep patlasin, sonra UC yedek saglayici
    # olsun - ama butce ZATEN dolmus olsun ki hicbiri gercekten CAGRILMASIN.
    monkeypatch.setitem(aura_brain.TEXT_PROVIDERS, aura_brain.TEXT_PROVIDER, _always_fails)
    monkeypatch.setattr(aura_brain, "AURA_BRAIN_URL", "")
    monkeypatch.setattr(aura_brain, "TOTAL_GENERATION_BUDGET_SECONDS", 0)

    called = []

    def _fake_chain():
        return [("fake_provider", lambda c, s: called.append(1) or "cevap")]

    monkeypatch.setattr(aura_brain, "_reasoning_fallback_chain", _fake_chain)

    with pytest.raises(_Boom):
        aura_brain.generate_with_retry([], "sistem talimati")

    # butce 0 oldugu icin yedek saglayici HIC CAGRILMAMALI.
    assert called == []


def test_fallback_chain_runs_normally_when_budget_not_exhausted(monkeypatch):
    monkeypatch.setitem(aura_brain.TEXT_PROVIDERS, aura_brain.TEXT_PROVIDER, _always_fails)
    monkeypatch.setattr(aura_brain, "AURA_BRAIN_URL", "")
    monkeypatch.setattr(aura_brain, "TOTAL_GENERATION_BUDGET_SECONDS", 45)

    def _fake_chain():
        return [("fake_provider", lambda c, s: "merhaba, ben yedek saglayici")]

    monkeypatch.setattr(aura_brain, "_reasoning_fallback_chain", _fake_chain)

    response = aura_brain.generate_with_retry([], "sistem talimati")
    assert response.text == "merhaba, ben yedek saglayici"


def test_budget_is_checked_before_each_fallback_not_only_once(monkeypatch):
    """Ikinci yedek denenmeden once butce kontrolu tekrar yapilmali - ilk
    yedek cok uzun surerse (ornek: kendi zaman asimina kadar beklerse),
    ikinci yedek hic denenmeden atlanmali."""
    monkeypatch.setitem(aura_brain.TEXT_PROVIDERS, aura_brain.TEXT_PROVIDER, _always_fails)
    monkeypatch.setattr(aura_brain, "AURA_BRAIN_URL", "")
    monkeypatch.setattr(aura_brain, "TOTAL_GENERATION_BUDGET_SECONDS", 0.05)

    calls = []

    def _slow_provider(c, s):
        import time
        time.sleep(0.2)  # butceyi (0.05sn) asiyor
        calls.append("slow")
        return ""  # bos/engellenmis yanit - zincir devam eder

    def _second_provider(c, s):
        calls.append("second")
        return "ikinci saglayicidan cevap"

    def _fake_chain():
        return [("slow", _slow_provider), ("second", _second_provider)]

    monkeypatch.setattr(aura_brain, "_reasoning_fallback_chain", _fake_chain)

    with pytest.raises(_Boom):
        aura_brain.generate_with_retry([], "sistem talimati")

    assert calls == ["slow"]  # ikinci saglayici HIC denenmedi
