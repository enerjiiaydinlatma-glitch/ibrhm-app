"""TURKCE INCELEME - videoda soylenenlerin Turkce cevirisi (operator Ingilizce bilmiyor; yayin karari insan incelemesine dayanir).

ONEMLI: bu ceviri YALNIZ inceleme icindir, videoya/altyazıya GIRMEZ. Makine cevirisidir; supheli yerde Ingilizce metin esastir.
Cevirmen talimati: ozetleme, ekleme, yumusatma YOK; sayilar, adlar, tirnaklar ayni kalir.
"""
import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SAGLAYICILAR = ("gemini", "groq", "openai", "anthropic", "xai")     # anahtari olan ilk saglayici kullanilir

SISTEM = ("You are a precise English-to-Turkish translator for a fact-checking editor who does not read English. "
          "Translate each numbered line into natural Turkish. Keep numbers, product and company names, units and quotation marks "
          "EXACTLY as written. Do NOT summarize, add, soften, explain, or merge lines. Output exactly one line per input line, "
          "using the same numbering format 'N. text'. Output nothing else.")
_SATIR = re.compile(r"^\s*(\d+)[.)]\s*(.*\S)?\s*$")


def _saglayici_sirasi():
    return list(SAGLAYICILAR)


def _varsayilan_caller(ad):
    from providers import PROVIDER_CALLERS
    return PROVIDER_CALLERS[ad]


def ceviri(metinler, saglayicilar=None, caller_al=None):
    """metinler: [en,...] -> {"tr":[...], "saglayici":ad, "eksik":[idx...], "hata": ""}. Hicbir saglayici calismazsa tr=[]."""
    metinler = [str(m) for m in metinler]
    if not any(m.strip() for m in metinler):
        return {"tr": [""] * len(metinler), "saglayici": "", "eksik": [], "hata": ""}
    caller_al = caller_al or _varsayilan_caller
    istek = [{"role": "user", "content": "\n".join(f"{i + 1}. {m}" for i, m in enumerate(metinler))}]
    hatalar = []
    for ad in (saglayicilar or _saglayici_sirasi()):
        try:
            cevap = caller_al(ad)(istek, SISTEM)
        except Exception as e:                       # noqa: BLE001  (anahtar yok / ag / kota): siradaki saglayici
            hatalar.append(f"{ad}: {type(e).__name__}")
            continue
        sonuc = {}
        for ln in (cevap or "").splitlines():
            m = _SATIR.match(ln)
            if m:
                sonuc[int(m.group(1))] = (m.group(2) or "").strip()
        tr = [sonuc.get(i + 1, "") for i in range(len(metinler))]
        eksik = [i for i, t in enumerate(tr) if not t and metinler[i].strip()]
        if len(eksik) <= len(metinler) // 2:          # makul olcude tamamsa kabul
            return {"tr": [t or "(çevrilemedi)" for t in tr], "saglayici": ad, "eksik": eksik, "hata": ""}
        hatalar.append(f"{ad}: eksik cikti")
    return {"tr": [], "saglayici": "", "eksik": [], "hata": "Ceviri yapilamadi (" + "; ".join(hatalar) + ")"}


def uretim_metni(gun=None, engine=None):
    """Bugunun (veya verilen gunun) uretiminin sesli/ekranda metni: run.json -> short. Yoksa None."""
    gun = gun or datetime.date.today().isoformat()
    yol = os.path.join(engine or os.path.join(HERE, "_engine"), gun, "run.json")
    try:
        with open(yol, encoding="utf-8") as f:
            run = json.load(f)
    except Exception:
        return None
    steps = run.get("steps", {}) if isinstance(run, dict) else {}
    short = run.get("short") or steps.get("short") or {}
    if not isinstance(short, dict) or not short:
        return None
    script = short.get("script") or ""
    satirlar = [s.strip() for s in (script if isinstance(script, str) else "\n".join(map(str, script))).splitlines() if s.strip()]
    aciklama = [s.strip() for s in str(short.get("description") or "").split("\n\n") if s.strip()][:2]
    return {"baslik": short.get("title") or "", "satirlar": satirlar, "aciklama": aciklama,
            "video_id": short.get("video_id") or "", "gizlilik": (short.get("sensitivity") or {})}
