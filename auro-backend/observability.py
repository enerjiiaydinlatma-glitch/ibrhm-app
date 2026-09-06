"""Cokme / hata takibi - Sentry sarmalayicisi (2026-09-06).

NEDEN: uclu AI danismasinin (Aura + Gemini + Groq, bkz. hafiza
"aura-launch-sequence-consult") "yayin oncesi pazarlik edilemez" dedigi
tek eksik parca buydu. metrics.py "su an sistem sagligi ne" anlik
gorunurlugu veriyor ama KALICI degil (restart'ta sifirlanir) ve
uyari/alarm yok. Bu modul o boslugu doldurur: yakalanmis-ama-yutulmus
hatalar (sohbet uretimi, akis, analiz) ve rota disina sizan 500'ler
Sentry'ye gider - orada gruplanir, saklanir, alarm uretir.

INERT VARSAYILAN: SENTRY_DSN ortam degiskeni TANIMLI DEGILSE bu modulun
hicbir fonksiyonu bir sey yapmaz (sessiz no-op). sentry-sdk kurulu
degilse de ayni. Yani DATABASE_URL kalibinin aynisi - kod canliya
girer, DSN baglanana kadar davranis degismez. Geri donus: SENTRY_DSN sil.

GIZLILIK: Aura bir ruh-esi/companion uygulamasi - kullanici mesajlari
ASLA Sentry'ye gitmemeli. send_default_pii=False + max_request_body_size
"never" bunu garantiler; before_send ekstra bir emniyet kemeri olarak
istek govdesini/cerezleri/Authorization basligini temizler.
"""
from __future__ import annotations

import os

try:  # sentry-sdk requirements'ta ama deploy gecikirse import patlamasin
    import sentry_sdk
except Exception:  # ImportError + olasi alt-bagimlilik hatalari
    sentry_sdk = None

_ENABLED = False


def _scrub_event(event: dict, _hint: dict) -> dict | None:
    """before_send: PII sizabilecek alanlari kes. send_default_pii=False
    zaten cogunu yapiyor; bu, govde/baslik/cerez icin acik ikinci kat."""
    try:
        req = event.get("request")
        if isinstance(req, dict):
            req.pop("data", None)
            req.pop("cookies", None)
            headers = req.get("headers")
            if isinstance(headers, dict):
                for k in list(headers):
                    if k.lower() in ("authorization", "cookie", "x-voice-key"):
                        headers[k] = "[kesildi]"
        event.pop("user", None)
    except Exception:
        pass
    return event


def init_sentry() -> bool:
    """main.py acilirken bir kez cagrilir. DSN yoksa/kutuphane yoksa
    sessizce False doner. Doner: etkinlestirildi mi."""
    global _ENABLED
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn or sentry_sdk is None:
        reason = "SENTRY_DSN yok" if not dsn else "sentry-sdk kurulu degil"
        print(f"[observability] Sentry pasif ({reason}) - hata takibi devre disi")
        return False

    try:
        traces_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0") or "0")
    except ValueError:
        traces_rate = 0.0

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=(os.getenv("SENTRY_ENVIRONMENT") or "production").strip(),
            release=(os.getenv("SENTRY_RELEASE") or "").strip() or None,
            # Kapali beta: performans izlemesi kapali (kota/maliyet),
            # sadece hatalar. Gerekirse env ile acilir.
            traces_sample_rate=traces_rate,
            send_default_pii=False,
            max_request_body_size="never",
            before_send=_scrub_event,
        )
    except Exception as e:  # kotu DSN vb. - acilis ASLA cokmesin
        print(f"[observability] Sentry init basarisiz ({type(e).__name__}: {e})")
        return False

    _ENABLED = True
    print("[observability] Sentry aktif - hata takibi acik")
    return True


def capture_exception(exc: BaseException, *, context: str = "") -> None:
    """Yakalanmis ama yutulmus bir istisnayi bildir (zarif dususler:
    sohbet uretimi, akis, analiz). context = kaba yer etiketi."""
    if not _ENABLED or sentry_sdk is None:
        return
    try:
        with sentry_sdk.new_scope() as scope:
            if context:
                scope.set_tag("aura.context", context)
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def capture_failure(event: str, detail: str = "") -> None:
    """metrics.record(ok=False) buradan gecer - bilinen hata siniflarinin
    (text_gen.*, bg_extraction.*, memory_write ...) toplu gorunurlugu.
    Yigin izi olan gercek istisnalar capture_exception'dan gelir."""
    if not _ENABLED or sentry_sdk is None:
        return
    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("aura.event", event)
            scope.set_level("error")
            sentry_sdk.capture_message(f"{event}: {detail}"[:500] if detail else event)
    except Exception:
        pass
