"""Hafif, bagimsizliksiz operasyonel metrik toplayici (2026-09-06).

BULUNDU (bu oturum): hafiza cikarimi ~1 saat production'da SESSIZCE
cokuyordu ve HICBIR gorunurluk yoktu - sadece uzun bir test yakaladi.
Bu modul o sinifi kapatir: saglayici cagrilarinin, hafiza yazmalarinin
ve hatalarin sayaclarini bellekte tutar; /api/admin/health bunlari
dondurur. Kalicilik YOK (restart'ta sifirlanir) - amac "su an sistem
sagligi ne" anlik gorunurlugu, tarihsel analitik degil (o zaten
/api/admin/stats + DB'de).

Thread-safe: uvicorn worker'lari ayni process icinde thread havuzu
kullaniyor, basit bir Lock yeterli.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

_LOCK = threading.Lock()
_START = time.time()

# olay -> {"ok": n, "fail": n}
_COUNTERS: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0})
# son N hata mesaji (teshis icin), halka tampon
_ERRORS: list[dict] = []
_ERRORS_MAX = 50


def record(event: str, ok: bool = True, detail: str = "") -> None:
    """Bir olayin sonucunu say. event ornek: 'text_gen.gemini',
    'text_gen.groq', 'bg_extraction.groq', 'bg_extraction.gemini',
    'memory_write', 'chat_request', 'voice_ws'."""
    try:
        with _LOCK:
            c = _COUNTERS[event]
            c["ok" if ok else "fail"] += 1
            if not ok:
                _ERRORS.append({
                    "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "event": event,
                    "detail": detail[:300],
                })
                if len(_ERRORS) > _ERRORS_MAX:
                    del _ERRORS[0]
    except Exception:
        # metrik toplama ASLA ana akisi bozmaz
        pass


def snapshot() -> dict:
    with _LOCK:
        counters = {k: dict(v) for k, v in _COUNTERS.items()}
        errors = list(_ERRORS)
    # tureilmis: her olay icin basari orani
    rates = {}
    for k, v in counters.items():
        total = v["ok"] + v["fail"]
        rates[k] = round(v["ok"] / total, 4) if total else None
    return {
        "uptime_seconds": int(time.time() - _START),
        "counters": counters,
        "success_rates": rates,
        "recent_errors": errors,
    }
