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
OLGUN_GUN = 3                                  # Shorts izlenmesi ilk gunlerde hizla artar: >=3 gunluk videolar sonuc sayilir
KOMSU_GUN = 10                                 # bir videoyu +-10 gun icindeki videolarin medyaniyla kiyasla
MIN_KOMSU = 3
MARKA = {"#shorts", "#signcouncil"}          # neredeyse her videoda: ayirt edici degil
TR_ETIKET = {"#ekonomi", "#etik", "#sentez", "#teknoloji", "#yapayzeka", "#yapayzekâ", "#gundem", "#gündem"}   # eski Turkce seri; kitle artik ABD


def _tarih(v):
    try:
        return datetime.date.fromisoformat(str(v.get("published", ""))[:10])
    except Exception:
        return None


def goreli(videolar):
    """Her videoya 'rel' ekler: izlenme / (kendi doneminin medyani). 1.0 = o donemde tipik video.
    Neden: kanalin erken donemi (Agu-Eyl basi) cok izlendi, sonra erisim %65 dustu; ham izlenme baslik/sutun etkisini
    ZAMAN etkisiyle karistirir. Komsu (+-KOMSU_GUN) en az MIN_KOMSU video yoksa tum videolarin medyani kullanilir."""
    genel = statistics.median([v.get("views", 0) for v in videolar]) if videolar else 0
    out = []
    for v in videolar:
        d = _tarih(v)
        komsu = [x.get("views", 0) for x in videolar if x is not v and d and _tarih(x) and abs((_tarih(x) - d).days) <= KOMSU_GUN]
        taban = statistics.median(komsu) if len(komsu) >= MIN_KOMSU else genel
        w = dict(v)
        w["rel"] = round(v.get("views", 0) / taban, 3) if taban else None
        out.append(w)
    return out


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
            "med_goreli": _med([v["rel"] for v in vids if v.get("rel") is not None]),
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
    for v in goreli(videolar):
        try:
            yas = (now - datetime.date.fromisoformat(str(v.get("published", ""))[:10])).days
        except Exception:
            yas = v.get("age_days", 99)
        if yas >= OLGUN_GUN:
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
        "hashtag": _hashtag_paketle(vs),
    }
    for v in vs:
        v.pop("_f", None)
    return {"genel": genel, "bolumler": bolumler, "oneriler": oneriler(genel, bolumler)}


def _hashtag_paketle(vs):
    """Ayni video kumesinde BIRLIKTE gecen hashtag'ler tek paket sayilir (ayri kanit degil; ornek: #Ekonomi/#Etik/#Risk/#Sentez
    ayni 9 videoda). Paket 'seri' isaretlenir ve oneride kullanilmaz. Turkce etiketler oneri disi."""
    kume = {}
    for v in vs:
        for h in (v.get("hashtags") or []):
            if h.lower() not in MARKA:
                kume.setdefault(h, set()).add(v["id"])
    paket = {}
    for h, ids in kume.items():
        paket.setdefault(frozenset(ids), []).append(h)
    rows = []
    for ids, adlar in paket.items():
        if len(ids) < 3:
            continue
        r = _satir("/".join(sorted(adlar)), [v for v in vs if v["id"] in ids])
        r["seri"] = len(adlar) > 1
        r["turkce"] = any(a.lower() in TR_ETIKET for a in adlar)
        rows.append(r)
    return sorted(rows, key=lambda r: (-r["n"], r["ad"]))[:15]


def oneriler(genel, bolumler):
    """Yalnizca n>=MIN_N ve belirgin fark (>=%30) olan gruplar; ZAMANA GORE duzeltilmis (goreli) medyanla; 'deneme' olarak."""
    out = []
    for ad, satirlar in bolumler.items():
        for r in satirlar:
            if r["n"] < MIN_N or ad == "gun" or r.get("med_goreli") is None or r.get("seri") or r.get("turkce"):
                continue
            oran = r["med_goreli"]
            etiket = f"{r['ad']}: kendi döneminin tipik videosunun {round(oran, 1)} katı izlenme (n={r['n']}, {r['guven']})."
            if oran >= 1.3:
                out.append({"tur": ad, "ad": r["ad"], "n": r["n"], "guven": r["guven"], "oran": round(oran, 2), "metin": etiket + " Deneme olarak öne al."})
            elif oran <= 0.7:
                out.append({"tur": ad, "ad": r["ad"], "n": r["n"], "guven": r["guven"], "oran": round(oran, 2), "metin": etiket + " Azaltmayı dene."})
    return sorted(out, key=lambda o: -abs(o["oran"] - 1))[:8]


def hashtag_onerisi(videolar, k=3, now=None):
    """3 ayirt edici hashtag (+ marka etiketleri her zaman). Yalniz n>=MIN_N olanlar; medyan izlenme ve tutmaya gore."""
    kr = karne(videolar, now)
    adaylar = [r for r in kr["bolumler"]["hashtag"]
               if r["n"] >= MIN_N and r["med_izlenme"] is not None and not r.get("seri") and not r.get("turkce")]
    adaylar.sort(key=lambda r: -((r.get("med_goreli") or 0) * 100 + 0.5 * (r["med_tutma"] or 0)))
    sec = adaylar[:k]
    return {"hashtagler": ["#Shorts"] + [r["ad"] for r in sec] + ["#SignCouncil"],
            "dayanak": [f"{r['ad']} (n={r['n']}, dönemine göre {r.get('med_goreli')}x, {r['guven']})" for r in sec],
            "not": "Örnek az: bunlar deneme önerisidir; her video 3 farklı etiketle çıkarsa karne zamanla netleşir."}


def kanal_tracker(t):
    """tracker.load() -> analiz.kanal_videolari() biciminde (sutun/analiz ayni veriyi kullansin)."""
    vids = []
    for v in goreli((t or {}).get("videos", [])):
        vids.append({"rel": v.get("rel"), "id": v["id"], "title": v.get("title", ""), "published": str(v.get("published", ""))[:10] + "T12:00:00Z",
                     "views": v.get("views", 0), "likes": v.get("likes", 0), "comments": v.get("comments", 0),
                     "shares": v.get("shares", 0), "subs": v.get("subs", 0), "retention": v.get("retention"),
                     "hashtags": v.get("hashtags", []), "privacy": "public"})
    return {"ok": bool(vids), "abone": None, "videolar": vids, "hata": "" if vids else "tracker verisi yok"}
