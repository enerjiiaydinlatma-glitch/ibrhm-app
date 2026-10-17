"""NIS TARAMA - belirli bir nisteki (afet / iklim / uzay / gelecek 'what if') herkese acik Shorts'lari tarar, kalip + etkilesim raporu cikarir.
YouTube'a HICBIR sey yazmaz. viral_analiz.py'nin API katmanini kullanir (ayri onbellek: AI-haber analizini bozmaz).

Kullanim:
  python nis_tarama.py --plan       # yalniz plan + tahmini kota (istek atmaz)
  python nis_tarama.py              # onbellek (24 saat) tazeyse onu kullanir, degilse API'den ceker; _engine/nis_afet_rapor.md yazar
  python nis_tarama.py --yenile     # onbellegi yok sayar (kota harcar: ~sorgu sayisi x 100 + yorumlar ~5)

Veri: yalniz HERKESE ACIK sayilar (izlenme/begeni/yorum/sure/baslik/abone) ve en cok izlenen birkac videonun ust duzey yorumlari (yalniz sizin ekraninizda/raporda;
LLM istemine GIRMEZ). Baska kanallarin CTR'si / ilk 3 saniye elde tutma verisi API'den GORULEMEZ: bunun icin raporun sonundaki izleme sablonunu doldurun.
Orneklem kucuk ve arama-yanli olabilir: sonuclar YON gostergesidir, kanit degil.
"""
import datetime
import json
import os
import re
import statistics
import sys

import viral_analiz as va

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = va.ENGINE
CACHE = os.path.join(ENGINE, "nis_afet.json")
RAPOR = os.path.join(ENGINE, "nis_afet_rapor.md")
CACHE_SAAT = 24
GUN = 90
YORUM_VIDEO = 5
YORUM_ADET = 20

SORGULAR_AFET = [
    "what if sea level rises", "what if all the ice melted", "melting glaciers what happens", "disaster scenario what if",
    "moon base future", "what if we lived on the moon", "flying cars future", "end of the world scenario",
]

KORKU = re.compile(r"\b(disaster|collapse|apocalypse|extinct\w*|surviv\w*|end of the world|catastroph\w*|doomsday|flood\w*|drown\w*|"
                   r"die[sd]?|dead|deadly|wipe\w* out|impossible|terrifying|scary|warning)\b", re.I)
WHAT_IF = re.compile(r"^\s*what if\b", re.I)
WOULD_YOU = re.compile(r"\b(would you|could you|can you|do you|will you)\b", re.I)
BUYUK_SAYI = re.compile(r"\b\d[\d,.]*\s?(?:cm|m|km|ft|feet|meters?|degrees|years?|%|percent|million|billion|mph)\b", re.I)

KONULAR = {
    "deniz/buz/iklim": r"sea level|ice|glacier|melt|climate|flood|ocean|polar|warming",
    "uzay/ay/mars": r"moon|mars|space|lunar|astronaut|orbit|colony|rocket|planet",
    "ucan araba/gelecek sehir": r"flying car|future city|self[- ]driving|robot|2050|2100|city of the future|hover",
    "dogal afet": r"earthquake|volcano|asteroid|tsunami|solar storm|hurricane|supervolcano|meteor",
}


def nis_ozellikleri(baslik):
    b = (baslik or "").strip()
    return {
        "what_if": bool(WHAT_IF.search(b)),
        "would_you": bool(WOULD_YOU.search(b)),
        "korku_kelimesi": bool(KORKU.search(b)),
        "sayi+birim": bool(BUYUK_SAYI.search(b)),
        "soru": "?" in b,
        "kisa(<=50)": len(b) <= 50,
    }


def kalip_raporu(satirlar, min_n=5):
    """nis_ozellikleri icin var/yok gruplarinin MEDYAN izlenmesi."""
    out = []
    if not satirlar:
        return out
    oz = [(s, nis_ozellikleri(s["baslik"])) for s in satirlar]
    for ad in oz[0][1]:
        var = [s["izlenme"] for s, f in oz if f[ad]]
        yok = [s["izlenme"] for s, f in oz if not f[ad]]
        mv, my = (statistics.median(var) if var else None), (statistics.median(yok) if yok else None)
        out.append({"ozellik": ad, "n_var": len(var), "medyan_var": mv, "n_yok": len(yok), "medyan_yok": my,
                    "oran": round(mv / my, 2) if (mv is not None and my) else None,
                    "az_ornek": len(var) < min_n or len(yok) < min_n})
    return sorted(out, key=lambda r: (r["az_ornek"], -(r["oran"] or 0)))


def konu_gruplari(satirlar, konular=KONULAR):
    """Konu kovasi -> n, medyan izlenme, medyan saatlik, en cok izlenen. Bir video birden cok kovaya girebilir; hicbirine girmeyen 'diger'."""
    kov = {ad: [] for ad in konular}
    kov["diger"] = []
    for s in satirlar:
        girdi = False
        for ad, kalip in konular.items():
            if re.search(kalip, s["baslik"], re.I):
                kov[ad].append(s)
                girdi = True
        if not girdi:
            kov["diger"].append(s)
    out = []
    for ad, grup in kov.items():
        if not grup:
            continue
        en = max(grup, key=lambda s: s["izlenme"])
        out.append({"konu": ad, "n": len(grup), "medyan_izlenme": statistics.median(s["izlenme"] for s in grup),
                    "medyan_saatlik": round(statistics.median(s["saatlik"] for s in grup), 2),
                    "en_cok": {"baslik": en["baslik"], "izlenme": en["izlenme"]}})
    return sorted(out, key=lambda r: -r["medyan_izlenme"])


def yorum_ozeti(yorumlar):
    """['yorum metni', ...] -> soru orani, 'ben/I' orani (kisisel cevap), ortalama kelime. Metin KOPYALANMAZ."""
    yorumlar = [y for y in (yorumlar or []) if (y or "").strip()]
    if not yorumlar:
        return {"n": 0}
    soru = sum(1 for y in yorumlar if "?" in y)
    kisisel = sum(1 for y in yorumlar if re.search(r"\b(i|i'd|i'm|i've|my|me)\b", y, re.I))
    return {"n": len(yorumlar), "soru_orani": round(soru / len(yorumlar), 2), "kisisel_orani": round(kisisel / len(yorumlar), 2),
            "ort_kelime": round(sum(len(y.split()) for y in yorumlar) / len(yorumlar), 1)}


def rapor_md(d, yorumlar=None, simdi=None):
    """d: viral_analiz.cek ciktisi; yorumlar: {video_id: [metin,...]}. -> Turkce Markdown."""
    sat = d["satirlar"]
    simdi = simdi or datetime.date.today()
    yorumlar = yorumlar or {}
    if not sat:
        return f"# Nis Taramasi ({simdi})\n\nVeri yok.\n"
    o = va.ozet(sat)
    s = [f"# Niş Taraması: afet / iklim / uzay / gelecek ({simdi})", "",
         f"Kaynak: YouTube herkese açık Shorts (≤{va.MAX_SURE} sn), son {d.get('gun', GUN)} gün, izlenmeye göre sıralı arama. "
         f"Sorgular: {', '.join(d['sorgular'])}.",
         "> Örneklem küçük ve arama-yanlı: YÖN göstergesidir, kanıt değil. İlk 3 saniye / görsel / elde tutma verisi API'den görülemez (sondaki şablon).", "",
         "## Özet", "",
         f"- {o['video']} video · medyan izlenme **{o['medyan_izlenme']}** · ortalama {o['ortalama_izlenme']} · en çok {o['en_cok']} · medyan süre {o['medyan_sure']} sn", ""]

    s += ["## En çok izlenen 15", "", "| İzlenme | Saatlik | Yorum‰ | Süre | Abone | Kanal | Başlık |", "|---|---|---|---|---|---|---|"]
    for r in sorted(sat, key=lambda x: -x["izlenme"])[:15]:
        s.append(f"| {r['izlenme']} | {r['saatlik']} | {r['yorum_orani']} | {r['sure']} | {r['abone']} | {r['kanal']} | {r['baslik']} |")

    kucuk = [r for r in sat if r["abone_orani"] is not None and r["abone"] and r["abone"] < 50000]
    s += ["", "## Küçük kanalda patlayanlar (izlenme/abone, abone < 50.000): bizim ölçeğe en yakın", "",
          "| Oran | İzlenme | Abone | Kanal | Başlık |", "|---|---|---|---|---|"]
    for r in sorted(kucuk, key=lambda x: -x["abone_orani"])[:10]:
        s.append(f"| {r['abone_orani']}x | {r['izlenme']} | {r['abone']} | {r['kanal']} | {r['baslik']} |")

    s += ["", "## Konu grupları (medyan izlenme)", "", "| Konu | n | Medyan izlenme | Medyan saatlik | En çok izlenen |", "|---|---|---|---|---|"]
    for r in konu_gruplari(sat):
        s.append(f"| {r['konu']} | {r['n']} | {r['medyan_izlenme']} | {r['medyan_saatlik']} | {r['en_cok']['baslik']} ({r['en_cok']['izlenme']}) |")

    s += ["", "## Başlık kalıpları (var / yok medyan izlenme)", "", "| Özellik | n var | Medyan var | n yok | Medyan yok | Oran | Not |", "|---|---|---|---|---|---|---|"]
    for r in kalip_raporu(sat):
        s.append(f"| {r['ozellik']} | {r['n_var']} | {r['medyan_var']} | {r['n_yok']} | {r['medyan_yok']} | {r['oran']} | {'az örnek' if r['az_ornek'] else ''} |")

    s += ["", "## Etkileşim: en çok izlenen videoların yorumları", ""]
    if not yorumlar:
        s.append("_Yorum çekilmedi (kapalı olabilir ya da API hatası)._")
    for r in sorted(sat, key=lambda x: -x["izlenme"])[:YORUM_VIDEO]:
        y = yorumlar.get(r["id"])
        if y is None:
            continue
        oz = yorum_ozeti(y)
        s.append(f"- **{r['baslik']}** ({r['izlenme']} izlenme, {r['yorum']} yorum): " +
                 (f"örnek {oz['n']} yorumun %{int(oz['soru_orani'] * 100)}'i soru, %{int(oz['kisisel_orani'] * 100)}'i kişisel cevap ('I/my'), ort. {oz['ort_kelime']} kelime"
                  if oz.get("n") else "yorum yok/kapalı"))
        for t in y[:4]:
            s.append(f"    - “{t.strip()[:140]}”")

    s += ["", "## Sen doldur: ilk 3 saniye / görsel (API göstermez)", "",
          "En çok izlenen 5 videoyu aç, her biri için yaz: (1) ilk 3 sn'de ne görünüyor/duyuluyor? (2) kanca soru mu, iddia mı, rakam mı? "
          "(3) görsel: gerçek çekim mi, yapay zekâ animasyonu mu, grafik mi? (4) tek anlatıcı mı, tartışma mı? (5) sonda çağrı var mı, ne diyor?", ""]
    for r in sorted(sat, key=lambda x: -x["izlenme"])[:5]:
        s.append(f"- https://youtu.be/{r['id']} ({r['izlenme']} izlenme, {r['sure']} sn)")
    return "\n".join(s) + "\n"


# --------------------------------------------------------------------------- API (yalniz okuma)
def yorumlari_cek(yt, satirlar, video_sayisi=YORUM_VIDEO, adet=YORUM_ADET):
    out = {}
    for r in sorted(satirlar, key=lambda x: -x["izlenme"])[:video_sayisi]:
        try:
            resp = yt.commentThreads().list(part="snippet", videoId=r["id"], maxResults=adet, order="relevance",
                                            textFormat="plainText").execute()
            out[r["id"]] = [it["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "") for it in resp.get("items", [])]
        except Exception:
            continue          # yorumlar kapali / kota / ag: o video atlanir
    return out


def _onbellek(now=None):
    now = now or datetime.datetime.utcnow()
    try:
        with open(CACHE, encoding="utf-8") as f:
            d = json.load(f)
        if (now - datetime.datetime.fromisoformat(d["zaman"])).total_seconds() < CACHE_SAAT * 3600:
            return d
    except Exception:
        pass
    return None


def main(argv):
    if "--plan" in argv:
        n = len(SORGULAR_AFET)
        print(f"Plan: {n} sorgu x search.list (100 birim) = {n * 100} birim + ~10 liste + ~{YORUM_VIDEO} yorum cagrisi. Hicbir istek atilmadi.")
        print("Sorgular:", ", ".join(SORGULAR_AFET))
        return 0
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = None if "--yenile" in argv else _onbellek()
    if d is None:
        try:
            d = va.cek(sorgular=SORGULAR_AFET, gun=GUN)
            d["yorumlar"] = yorumlari_cek(va._yt(), d["satirlar"])
        except Exception as e:  # noqa: BLE001
            print(f"[HATA] YouTube verisi alinamadi: {type(e).__name__}: {str(e)[:200]}")
            return 1
        os.makedirs(ENGINE, exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        print("(yeni cekildi)")
    else:
        print(f"(onbellek: {d['zaman']} UTC; yenilemek icin --yenile)")
    md = rapor_md(d, d.get("yorumlar"))
    os.makedirs(ENGINE, exist_ok=True)
    with open(RAPOR, "w", encoding="utf-8-sig") as f:
        f.write(md)
    print(md)
    print(f"Rapor dosyasi: {RAPOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
