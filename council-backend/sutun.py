"""ICERIK SUTUNLARI - hangi sutunla uretecegiz? Karar kanalin KENDI sonuclarindan gelir.

Sutunlar (motorun mevcut bayraklari):
  ikilem     --council-decides   izleyici ikilemi; yorum oylamasi motorda hazir (council_standings)
  siralama   --leaderboard       siralama / guc listesi
  aciklayici --evergreen         zamansiz mekanizma anlatimi (hafta sonu)
  receipt    (kaynak paketi)     belge kontrolu: tek iddia, tek birincil belge

Secim: her sutun >= MIN_DENEME kez denenmeden hicbiri elenmez (veri az; ~birkac izlenme gurultudur).
Yeterli veri varsa: %70 su ana kadar en iyi sutun, %30 en az denenen (kesif). Tohum = tarih (ayni gun ayni oneri).
Sonuc olcutu: ortalama izlenme + yorum (yorum x 20 agirlikli). Bu bir TAHMIN degil, gecmis sonuctur.
"""
import datetime
import json
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
GECMIS_YOL = os.path.join(ENGINE, "sutun_gecmis.jsonl")

SUTUNLAR = {
    "ikilem": {"ad": "İkilem (Konsey Karar Veriyor)", "bayrak": ["--council-decides"], "kaynak": False},
    "siralama": {"ad": "Sıralama / haber", "bayrak": ["--leaderboard"], "kaynak": False},
    "receipt": {"ad": "Receipt (belge kontrolü)", "bayrak": [], "kaynak": True},
    "aciklayici": {"ad": "Açıklayıcı (zamansız)", "bayrak": ["--evergreen"], "kaynak": False},
}
HAFTA_ICI = ["ikilem", "siralama", "receipt"]          # operator karari: ilk hafta bu uc, donusumlu
HAFTA_SONU = ["ikilem", "siralama", "receipt", "aciklayici"]
MIN_DENEME = 3
SOMURU = 0.70
YORUM_AGIRLIK = 20
OLGUNLUK_SAAT = 24      # bir video sonucu en az bu kadar sure sonra sayilir

_ETIKET = [
    ("receipt", re.compile(r"receipt|fail inspection|claims? checked|says otherwise|graded its own|the filing says|own benchmark", re.I)),
    ("ikilem", re.compile(r"council (?:case|decides)|should i|the council decides|dilemma", re.I)),
    ("aciklayici", re.compile(r"^what (?:is|are)\b|^how (?:does|do)\b|explained|\bexplainer\b", re.I)),
    ("siralama", re.compile(r"\brank|leaderboard|top \d|#1|jumps to|power list|\bvs\.? ", re.I)),
]


def etiketle(baslik):
    """Gecmis videolari sutuna ata (baslik kalibindan). Eslesmezse 'diger'."""
    for ad, rx in _ETIKET:
        if rx.search(baslik or ""):
            return ad
    return "diger"


def aktif_sutunlar(bugun=None):
    bugun = bugun or datetime.date.today()
    return list(HAFTA_SONU if bugun.weekday() >= 5 else HAFTA_ICI)


# ----------------------------------------------------------------------------- kayit
def kaydet(video_id, sutun, zaman=None):
    """Uretilen videoyu sutuna bagla (motor video_id verdikten sonra)."""
    try:
        os.makedirs(ENGINE, exist_ok=True)
        with open(GECMIS_YOL, "a", encoding="utf-8") as f:
            f.write(json.dumps({"video_id": video_id, "sutun": sutun,
                                "zaman": zaman or datetime.datetime.now().isoformat(timespec="seconds")}) + "\n")
    except Exception:
        pass


def kayitlar():
    out = {}
    try:
        with open(GECMIS_YOL, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                    out[r["video_id"]] = r["sutun"]
                except Exception:
                    continue
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------- istatistik
def _yas_saat(yayin, now):
    try:
        t = datetime.datetime.fromisoformat(yayin.replace("Z", "+00:00")).replace(tzinfo=None)
        return (now - t).total_seconds() / 3600.0
    except Exception:
        return None


def istatistik(videolar, kayit=None, now=None):
    """videolar: analiz.kanal_videolari()['videolar']. Sutun -> {deneme, ort_izlenme, ort_yorum, skor}.
    Etiket: kayitli (motorla uretilen) varsa o, yoksa baslik kalibi. Yalnizca public ve >= OLGUNLUK_SAAT."""
    now = now or datetime.datetime.utcnow()
    kayit = kayit if kayit is not None else kayitlar()
    tablo = {}
    for v in videolar:
        if v.get("privacy", "public") != "public":
            continue
        yas = _yas_saat(v.get("published", ""), now)
        if yas is None or yas < OLGUNLUK_SAAT:
            continue
        s = kayit.get(v["id"]) or etiketle(v["title"])
        t = tablo.setdefault(s, {"deneme": 0, "izlenme": 0, "yorum": 0, "ornek": []})
        t["deneme"] += 1
        t["izlenme"] += v.get("views", 0)
        t["yorum"] += v.get("comments", 0)
        if len(t["ornek"]) < (12 if s == "diger" else 2):
            t["ornek"].append(v["title"][:60])
    for t in tablo.values():
        n = max(t["deneme"], 1)
        t["ort_izlenme"] = round(t["izlenme"] / n, 1)
        t["ort_yorum"] = round(t["yorum"] / n, 2)
        t["skor"] = round(t["ort_izlenme"] + YORUM_AGIRLIK * t["ort_yorum"], 1)
    return tablo


def oner(tablo, bugun=None):
    """-> {sutun, neden, mod:'veri-topla'|'somur'|'kesif', tablo_satirlari}"""
    bugun = bugun or datetime.date.today()
    aktif = aktif_sutunlar(bugun)
    n = {s: tablo.get(s, {}).get("deneme", 0) for s in aktif}
    eksik = [s for s in aktif if n[s] < MIN_DENEME]
    if eksik:
        s = min(eksik, key=lambda x: (n[x], aktif.index(x)))
        return {"sutun": s, "mod": "veri-topla",
                "neden": f"{SUTUNLAR[s]['ad']} henüz {n[s]}/{MIN_DENEME} kez denendi; karar vermek için her sütun en az {MIN_DENEME} kez denenir."}
    en_iyi = max(aktif, key=lambda x: tablo[x]["skor"])
    rng = random.Random(bugun.isoformat())
    if rng.random() < SOMURU:
        return {"sutun": en_iyi, "mod": "somur",
                "neden": f"{SUTUNLAR[en_iyi]['ad']} şimdiye dek en iyi sonucu verdi (skor {tablo[en_iyi]['skor']}: ort. {tablo[en_iyi]['ort_izlenme']} izlenme, {tablo[en_iyi]['ort_yorum']} yorum)."}
    diger = [s for s in aktif if s != en_iyi] or aktif
    s = min(diger, key=lambda x: (n[x], aktif.index(x)))
    return {"sutun": s, "mod": "kesif", "neden": f"Keşif günü (%{int((1-SOMURU)*100)}): {SUTUNLAR[s]['ad']} daha az denendi ({n[s]} video)."}


def satirlar(tablo, aktif=None):
    aktif = aktif or aktif_sutunlar()
    out = []
    for s in list(SUTUNLAR) + ["diger"]:
        t = tablo.get(s)
        out.append({"sutun": s, "ad": SUTUNLAR.get(s, {}).get("ad", "Diğer / sınıflanamadı"), "aktif": s in aktif,
                    "deneme": t["deneme"] if t else 0, "ort_izlenme": t["ort_izlenme"] if t else None,
                    "ort_yorum": t["ort_yorum"] if t else None, "skor": t["skor"] if t else None,
                    "ornek": t["ornek"] if t else []})
    return out
