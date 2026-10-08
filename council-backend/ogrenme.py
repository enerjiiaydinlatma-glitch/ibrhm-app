"""OGRENME KARNESI - 'ne ise yaradi?' (sutun, baslik kalibi, hashtag, yayin gunu).

Girdi: tracker.load()['videos'] (her video: id, title, published 'YYYY-MM-DD', views, likes, comments, shares,
retention (% tutma/ort. izlenme orani; Shorts dongusunde 100'u asabilir), subs, tags, hashtags).

Ilkeler:
- MEDYAN kullanilir (tek bir viral video ortalamayi bozar); ortalama yalniz bilgi icin.
- Her satirda ornek sayisi (n) ve guven etiketi var: n<5 'cok az', 5-9 'yon', >=10 'daha guvenilir'. KANIT degil YON.
- Marka etiketleri (her videoda bulunan) karsilastirmaya girmez: ayirt edici degiller.
- Oneriler yalniz yeterli ornekte (n>=5) yapilir ve 'deneme' olarak sunulur; hicbir sey otomatik uygulanmaz.
"""
import datetime
import re
import statistics

import sutun

MIN_N = 5
GUVENILIR_N = 10
MARKA = {"#shorts", "#signcouncil"}          # neredeyse her videoda: ayirt edici degil


def _med(x):
    return round(statistics.median(x), 1) if x else None


def guven(n):
    return "çok az" if n < MIN_N else ("yön" if n < GUVENILIR_N else "daha güvenilir")


def ozellikler(v):
    t = v.get("title", "") or ""
    kelime = len(t.split())
    return {
        "sutun": sutun.etiketle(t),
        "sayi": "başlıkta sayı var" if re.search(r"\d", t) else "başlıkta sayı yok",
        "soru": "soru başlığı" if "?" in t else "ifade başlığı",
        "uzunluk": "kısa (≤8 kelime)" if kelime <= 8 else ("orta (9-12)" if kelime <= 12 else "uzun (13+)"),
        "gun": _gun(v.get("published", "")),
    }


def _gun(tarih):
    try:
        return ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"][datetime.date.fromisoformat(str(tarih)[:10]).weekday()]
    except Exception:
        return "?"


def _satir(ad, vids):
    n = len(vids)
    toplam_izl = sum(v.get("views", 0) for v in vids)
    return {"ad": ad, "n": n, "guven": guven(n),
            "med_izlenme": _med([v.get("views", 0) for v in vids]),
            "med_tutma": _med([v.get("retention", 0) for v in vids if v.get("retention") is not None]),
            "abone_1000": round(1000 * sum(v.get("subs", 0) for v in vids) / toplam_izl, 2) if toplam_izl else None,
            "yorum_1000": round(1000 * sum(v.get("comments", 0) for v in vids) / toplam_izl, 2) if toplam_izl else None}


def _grupla(videolar, anahtar):
    g = {}
    for v in videolar:
        for k in anahtar(v):
            g.setdefault(k, []).append(v)
    return sorted((_satir(k, vs) for k, vs in g.items()), key=lambda r: (-r["n"], r["ad"]))


def karne(videolar, now=None):
    """Tum bolumler. Taze (<24s) videolar sonuc sayilmaz."""
    now = now or datetime.date.today()
    vs = []
    for v in videolar:
        try:
            yas = (now - datetime.date.fromisoformat(str(v.get("published", ""))[:10])).days
        except Exception:
            yas = v.get("age_days", 99)
        if yas >= 1:
            vs.append(v)
    for v in vs:
        v["_f"] = ozellikler(v)
    genel = _satir("Tüm videolar", vs)
    bolumler = {
        "sutun": _grupla(vs, lambda v: [v["_f"]["sutun"]]),
        "sayi": _grupla(vs, lambda v: [v["_f"]["sayi"]]),
        "soru": _grupla(vs, lambda v: [v["_f"]["soru"]]),
        "uzunluk": _grupla(vs, lambda v: [v["_f"]["uzunluk"]]),
        "gun": _grupla(vs, lambda v: [v["_f"]["gun"]]),
        "hashtag": [r for r in _grupla(vs, lambda v: [h for h in (v.get("hashtags") or []) if h.lower() not in MARKA])
                    if r["n"] >= 3][:15],
    }
    for v in vs:
        v.pop("_f", None)
    return {"genel": genel, "bolumler": bolumler, "oneriler": oneriler(genel, bolumler)}


def oneriler(genel, bolumler):
    """Yalnizca n>=MIN_N ve belirgin fark (>=%30) olan gruplar; 'deneme' olarak."""
    out = []
    taban = genel.get("med_izlenme") or 0
    for ad, satirlar in bolumler.items():
        for r in satirlar:
            if r["n"] < MIN_N or not taban or ad == "gun":
                continue
            oran = (r["med_izlenme"] or 0) / taban
            if oran >= 1.3:
                out.append({"tur": ad, "ad": r["ad"], "n": r["n"], "guven": r["guven"], "oran": round(oran, 2),
                            "metin": f"{r['ad']}: medyan izlenme tüm videoların {round(oran, 1)} katı (n={r['n']}, {r['guven']}). Deneme olarak öne al."})
            elif oran <= 0.7:
                out.append({"tur": ad, "ad": r["ad"], "n": r["n"], "guven": r["guven"], "oran": round(oran, 2),
                            "metin": f"{r['ad']}: medyan izlenme tüm videoların {round(oran, 1)} katı (n={r['n']}, {r['guven']}). Azaltmayı dene."})
    return sorted(out, key=lambda o: -abs(o["oran"] - 1))[:8]


def hashtag_onerisi(videolar, k=3, now=None):
    """3 ayirt edici hashtag (+ marka etiketleri her zaman). Yalniz n>=MIN_N olanlar; medyan izlenme ve tutmaya gore."""
    kr = karne(videolar, now)
    adaylar = [r for r in kr["bolumler"]["hashtag"] if r["n"] >= MIN_N and r["med_izlenme"] is not None]
    adaylar.sort(key=lambda r: -((r["med_izlenme"] or 0) + 0.5 * (r["med_tutma"] or 0)))
    sec = adaylar[:k]
    return {"hashtagler": ["#Shorts"] + [r["ad"] for r in sec] + ["#SignCouncil"],
            "dayanak": [f"{r['ad']} (n={r['n']}, medyan {r['med_izlenme']} izlenme, {r['guven']})" for r in sec],
            "not": "Örnek az: bunlar deneme önerisidir; her video 3 farklı etiketle çıkarsa karne zamanla netleşir."}


def kanal_tracker(t):
    """tracker.load() -> analiz.kanal_videolari() biciminde (sutun/analiz ayni veriyi kullansin)."""
    vids = []
    for v in (t or {}).get("videos", []):
        vids.append({"id": v["id"], "title": v.get("title", ""), "published": str(v.get("published", ""))[:10] + "T12:00:00Z",
                     "views": v.get("views", 0), "likes": v.get("likes", 0), "comments": v.get("comments", 0),
                     "shares": v.get("shares", 0), "subs": v.get("subs", 0), "retention": v.get("retention"),
                     "hashtags": v.get("hashtags", []), "privacy": "public"})
    return {"ok": bool(vids), "abone": None, "videolar": vids, "hata": "" if vids else "tracker verisi yok"}
