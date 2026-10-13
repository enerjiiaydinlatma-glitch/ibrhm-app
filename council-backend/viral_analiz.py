"""NISTE NE PATLADI - son 7 gunun en cok izlenen AI-haber Shorts'lari ve kalip analizi. YouTube'a HICBIR sey yazmaz.

Kullanim:
  python viral_analiz.py              # onbellek (6 saat) tazeyse onu gosterir, degilse API'den ceker
  python viral_analiz.py --yenile     # onbellegi yok sayip yeniden ceker (API kotasi harcar)
  python viral_analiz.py --konu       # yalniz onbellekten raporu yazdirir (API istegi YOK)
  python viral_analiz.py --plan       # sadece plan + tahmini kota (hicbir istek atmaz)

Kota: her sorgu search.list = 100 birim; videos/channels listeleri ~1 birim. 8 sorgu ~ 810 birim (gunluk 10.000).
Veri: yalniz HERKESE ACIK sayilar (izlenme/begeni/yorum/sure/baslik/abone). Baska kanallarin CTR'si ve ilk-3-saniye verisi
API'den GORULEMEZ (yalniz kendi kanalinda); o kisim icin izleme sablonu yazdirilir.
Kural: orneklem kucukse (n<5) kalip tablosu 'AZ ORNEK' der - kanit degil, yon gostergesidir.
"""
import datetime
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
CACHE = os.path.join(ENGINE, "viral_son.json")
CACHE_SAAT = 6
GUN = 7
MAX_SURE = 65  # saniye: Shorts
SORGULAR = ["AI news", "OpenAI", "Anthropic Claude", "Nvidia AI", "Google Gemini", "AI safety", "AI agents", "ChatGPT"]
SORU_KELIME = ("why", "how", "is", "are", "did", "does", "do", "can", "will", "should", "what", "who", "when")
SIRALAMA = re.compile(r"\b(rank|ranks|ranking|#1|top|beats|beat|vs|overtakes|overtake|ahead|leader|leads|wins|race)\b", re.I)


VARLIKLAR = {  # konu (varlik) -> baslikta aranan kalip
    "ChatGPT/OpenAI": r"chat\s*gpt|\bgpt[- ]?\d|openai|\bsora\b|altman",
    "Gemini/Google": r"gemini|google|deepmind|pichai|\bveo\b",
    "Claude/Anthropic": r"claude|anthropic|amodei",
    "Nvidia": r"nvidia|jensen|\bgpu\b|blackwell|cuda",
    "Meta/Llama": r"\bmeta\b|llama|zuckerberg",
    "Grok/xAI/Musk": r"grok|\bxai\b|musk",
    "Apple": r"\bapple\b|siri|iphone",
    "Microsoft/Copilot": r"microsoft|copilot|\bbing\b",
    "DeepSeek/Cin": r"deepseek|china|chinese|qwen",
    "AI guvenlik/duzenleme": r"safety|regulat|\blaw\b|\bban\b|midterm|election|copyright|lawsuit|privacy",
    "AI ajanlar/is": r"\bagents?\b|\bjobs?\b|replace|automation|workers?",
}
HIZLI_YAS_SAAT = 72


# --------------------------------------------------------------------------- saf fonksiyonlar (testli)
def konu_raporu(satirlar):
    """Varlik/konu bazinda: video sayisi, toplam izlenme, MEDYAN saatlik izlenme, en hizli video. Bir video birden cok konuya girebilir."""
    out = []
    for ad, kalip in VARLIKLAR.items():
        rx = re.compile(kalip, re.I)
        grup = [s for s in satirlar if rx.search(s.get("baslik", ""))]
        if not grup:
            continue
        en = max(grup, key=lambda s: s["saatlik"])
        out.append({"konu": ad, "n": len(grup), "toplam_izlenme": sum(s["izlenme"] for s in grup),
                    "medyan_saatlik": round(statistics.median(s["saatlik"] for s in grup), 1),
                    "en_hizli": {"baslik": en["baslik"], "saatlik": en["saatlik"], "id": en["id"], "abone": en.get("abone")}})
    return sorted(out, key=lambda r: -r["medyan_saatlik"])


def hizli_yukselen(satirlar, en_fazla=10, yas_sinir=HIZLI_YAS_SAAT):
    """Taze (yas <= yas_sinir saat) ve SAATLIK izlenmesi en yuksek videolar = su an yukselen trend."""
    taze = [s for s in satirlar if s["yas_saat"] <= yas_sinir]
    return sorted(taze, key=lambda s: -s["saatlik"])[:en_fazla]

def sure_saniye(iso):
    """'PT1M5S' -> 65. Bozuksa None."""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def baslik_ozellikleri(baslik):
    b = (baslik or "").strip()
    ilk = (re.findall(r"[A-Za-z']+", b) or [""])[0].lower()
    harf = [c for c in b if c.isalpha()]
    buyuk = (sum(1 for c in harf if c.isupper()) / len(harf)) if harf else 0.0
    return {
        "soru": ilk in SORU_KELIME or "?" in b,
        "sayi": any(c.isdigit() for c in b),
        "iki_nokta": ":" in b,
        "siralama": bool(SIRALAMA.search(b)),
        "cok_buyuk_harf": buyuk > 0.3,
        "kisa_baslik": len(b) <= 50,
        "hashtag": "#" in b,
    }


def satir_hazirla(video, kanal_abone, now):
    """video: videos.list ogesi. -> analiz satiri (Shorts degilse None)."""
    sure = sure_saniye((video.get("contentDetails") or {}).get("duration"))
    if sure is None or sure > MAX_SURE:
        return None
    sn = video.get("snippet") or {}
    st = video.get("statistics") or {}
    try:
        t = datetime.datetime.fromisoformat(sn.get("publishedAt", "").replace("Z", "+00:00")).replace(tzinfo=None)
        yas_saat = max((now - t).total_seconds() / 3600.0, 1.0)
    except Exception:
        return None
    views = int(st.get("viewCount", 0) or 0)
    likes = int(st.get("likeCount", 0) or 0)
    yorum = int(st.get("commentCount", 0) or 0)
    return {
        "id": video["id"], "baslik": sn.get("title", ""), "kanal": sn.get("channelTitle", ""), "kanal_id": sn.get("channelId", ""),
        "yas_saat": round(yas_saat, 1), "sure": sure, "izlenme": views, "begeni": likes, "yorum": yorum,
        "saatlik": round(views / yas_saat, 2),
        "abone": kanal_abone, "abone_orani": round(views / kanal_abone, 2) if kanal_abone else None,
        "begeni_orani": round(100.0 * likes / views, 2) if views else None,
        "yorum_orani": round(100.0 * yorum / views, 3) if views else None,
        "ozellik": baslik_ozellikleri(sn.get("title", "")),
    }


def kalip_raporu(satirlar, min_n=5):
    """Her baslik ozelligi icin: var/yok gruplarinin MEDYAN izlenmesi. n<min_n ise az_ornek."""
    out = []
    if not satirlar:
        return out
    for ad in satirlar[0]["ozellik"]:
        var = [s["izlenme"] for s in satirlar if s["ozellik"][ad]]
        yok = [s["izlenme"] for s in satirlar if not s["ozellik"][ad]]
        mv = statistics.median(var) if var else None
        my = statistics.median(yok) if yok else None
        out.append({"ozellik": ad, "n_var": len(var), "medyan_var": mv, "n_yok": len(yok), "medyan_yok": my,
                    "oran": round(mv / my, 2) if (mv is not None and my) else None,
                    "az_ornek": len(var) < min_n or len(yok) < min_n})
    return sorted(out, key=lambda r: (r["az_ornek"], -(r["oran"] or 0)))


def ozet(satirlar):
    if not satirlar:
        return {"video": 0}
    v = [s["izlenme"] for s in satirlar]
    return {"video": len(satirlar), "medyan_izlenme": statistics.median(v), "ortalama_izlenme": round(sum(v) / len(v), 1),
            "en_cok": max(v), "medyan_sure": statistics.median(s["sure"] for s in satirlar)}


# --------------------------------------------------------------------------- API
def _yt():
    from googleapiclient.discovery import build
    from youtube_auth import get_credentials
    return build("youtube", "v3", credentials=get_credentials())


def cek(sorgular=SORGULAR, gun=GUN, now=None):
    now = now or datetime.datetime.utcnow()
    yt = _yt()
    after = (now - datetime.timedelta(days=gun)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = []
    for q in sorgular:
        r = yt.search().list(part="id", q=q, type="video", videoDuration="short", order="viewCount",
                             publishedAfter=after, relevanceLanguage="en", maxResults=25).execute()
        ids += [i["id"]["videoId"] for i in r.get("items", []) if i.get("id", {}).get("videoId")]
    ids = list(dict.fromkeys(ids))
    videolar = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        videolar += r.get("items", [])
    kanal_ids = list(dict.fromkeys(v["snippet"]["channelId"] for v in videolar))
    abone = {}
    for i in range(0, len(kanal_ids), 50):
        r = yt.channels().list(part="statistics", id=",".join(kanal_ids[i:i + 50])).execute()
        for c in r.get("items", []):
            st = c.get("statistics", {})
            abone[c["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0)
    satirlar = [s for s in (satir_hazirla(v, abone.get(v["snippet"]["channelId"]), now) for v in videolar) if s]
    return {"zaman": now.isoformat(timespec="seconds"), "gun": gun, "sorgular": list(sorgular), "satirlar": satirlar}


def nis_ozeti(d, max_yas_saat=72, now=None, min_n=5):
    """Konsey brifingi icin kucuk ve GUVENLI ozet. Ham baslik / kanal adi / URL ICERMEZ (baskasinin metni LLM istemine girmesin);
    yalniz kendi sozlugumuzdeki konu adlari ve sayilar. Onbellek yoksa/bozuksa/eskiyse None."""
    now = now or datetime.datetime.utcnow()
    try:
        t = datetime.datetime.fromisoformat(d["zaman"])
        if (now - t).total_seconds() > max_yas_saat * 3600:
            return None
        sat = d["satirlar"]
    except Exception:
        return None
    if not sat:
        return None
    konular = [{"konu": r["konu"], "video": r["n"], "medyan_saatlik_izlenme": r["medyan_saatlik"]}
               for r in konu_raporu(sat) if r["n"] >= min_n][:5]
    kaliplar = [{"baslik_ozelligi": r["ozellik"], "medyan_orani": r["oran"], "n_var": r["n_var"], "n_yok": r["n_yok"]}
                for r in kalip_raporu(sat, min_n=min_n) if not r["az_ornek"] and r["oran"] is not None]
    return {"kaynak": "YouTube herkese acik Shorts, son 7 gun (en cok izlenenler)", "video": len(sat),
            "medyan_izlenme": ozet(sat).get("medyan_izlenme"), "hizli_konular": konular, "baslik_kaliplari": kaliplar,
            "uyari": "Arama sonucu ornegi; eglence icerigi agirlikta olabilir. YON gostergesidir, kanit degil."}


def yukle_onbellek(now=None):
    now = now or datetime.datetime.utcnow()
    try:
        with open(CACHE, encoding="utf-8") as f:
            d = json.load(f)
        t = datetime.datetime.fromisoformat(d["zaman"])
        if (now - t).total_seconds() < CACHE_SAAT * 3600:
            return d
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- cikti
def _a(s, n):
    return (s or "").encode("ascii", "replace").decode("ascii")[:n]


def yazdir(d):
    sat = d["satirlar"]
    o = ozet(sat)
    print(f"\n{o.get('video', 0)} Shorts (<= {MAX_SURE} sn), son {d['gun']} gun, sorgular: {', '.join(d['sorgular'])}")
    if not sat:
        print("Veri yok.")
        return
    print(f"Medyan izlenme: {o['medyan_izlenme']}  |  ortalama: {o['ortalama_izlenme']}  |  en cok: {o['en_cok']}  |  medyan sure: {o['medyan_sure']} sn")

    print("\n=== EN COK IZLENEN 15 ===")
    print("izlenme  saatlik  begeni%  yorum%  sure  abone   kanal / baslik")
    for s in sorted(sat, key=lambda x: -x["izlenme"])[:15]:
        print(f"{s['izlenme']:>7}  {s['saatlik']:>7}  {str(s['begeni_orani']):>7}  {str(s['yorum_orani']):>6}  {s['sure']:>4}  {str(s['abone']):>6}  {_a(s['kanal'], 18)} | {_a(s['baslik'], 60)}")

    kucuk = [s for s in sat if s["abone_orani"] is not None and s["abone"] and s["abone"] < 50000]
    print("\n=== KUCUK KANALDA PATLAYANLAR (izlenme/abone orani; abone < 50.000) ===")
    for s in sorted(kucuk, key=lambda x: -x["abone_orani"])[:10]:
        print(f"{s['abone_orani']:>6}x  izlenme {s['izlenme']:>7}  abone {s['abone']:>6}  {_a(s['kanal'], 16)} | {_a(s['baslik'], 62)}")

    print("\n=== BASLIK KALIPLARI (var / yok medyan izlenme) ===")
    print("ozellik          n_var  medyan_var  n_yok  medyan_yok  oran   not")
    for r in kalip_raporu(sat):
        print(f"{r['ozellik']:<16} {r['n_var']:>5}  {str(r['medyan_var']):>10}  {r['n_yok']:>5}  {str(r['medyan_yok']):>10}  {str(r['oran']):>5}  {'AZ ORNEK' if r['az_ornek'] else ''}")

    print(f"\n=== SU AN YUKSELEN (yas <= {HIZLI_YAS_SAAT} saat; saatlik izlenme) ===")
    print("saatlik  izlenme  yas_s  abone   kanal / baslik")
    for s in hizli_yukselen(sat):
        print(f"{s['saatlik']:>7}  {s['izlenme']:>7}  {s['yas_saat']:>5.0f}  {str(s['abone']):>6}  {_a(s['kanal'], 16)} | {_a(s['baslik'], 62)}")

    print("\n=== KONU (VARLIK) RAPORU (medyan saatlik izlenmeye gore; bir video birden cok konuya girebilir) ===")
    print("konu                   n   toplam_izlenme  medyan_saatlik  en hizli video")
    for r in konu_raporu(sat):
        print(f"{r['konu']:<22} {r['n']:>3}  {r['toplam_izlenme']:>14}  {r['medyan_saatlik']:>14}  {_a(r['en_hizli']['baslik'], 52)} ({r['en_hizli']['saatlik']}/sa)")

    print("\n=== ILK 3 SANIYE / GORSEL: SENIN IZLEYIP NOT ALACAGIN SABLON (API bunu GOSTEREMEZ) ===")
    print("En cok izlenen 5 videoyu ac, her biri icin yaz: (1) ilk 3 sn'de ne gorunuyor/duyuluyor? (2) kanca bir soru mu, iddia mi, rakam mi?")
    print("(3) gorsel: yuz/metin/grafik? (4) tek konusmaci mi, tartisma mi? (5) sonda cagri var mi?")
    for s in sorted(sat, key=lambda x: -x["izlenme"])[:5]:
        print(f"  https://youtu.be/{s['id']}   ({s['izlenme']} izlenme, {s['sure']} sn)")
    print("\nNot: ornek kucuk/yanli olabilir (arama sonucu, izlenmeye gore). Oranlar YON gostergesidir, kanit degil.")


def main(argv):
    if "--plan" in argv:
        n = len(SORGULAR)
        print(f"Plan: {n} sorgu x search.list (100 birim) = {n * 100} birim + ~10 birim liste cagrilari. Hicbir istek atilmadi.")
        print("Sorgular:", ", ".join(SORGULAR))
        return 0
    if "--konu" in argv:   # yalniz onbellek, API istegi YOK
        try:
            with open(CACHE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            print("Onbellek yok: once  python viral_analiz.py  calistir.")
            return 1
        print(f"(onbellek: {d['zaman']} UTC; API istegi atilmadi)")
        yazdir(d)
        return 0
    d = None if "--yenile" in argv else yukle_onbellek()
    if d is None:
        try:
            d = cek()
        except Exception as e:  # noqa: BLE001
            print(f"[HATA] YouTube verisi alinamadi: {type(e).__name__}: {str(e)[:200]}")
            return 1
        os.makedirs(ENGINE, exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        print("(yeni cekildi; ~810 kota birimi)")
    else:
        print(f"(onbellek: {d['zaman']} UTC; yenilemek icin --yenile)")
    yazdir(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
