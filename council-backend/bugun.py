"""BUGUN - tek ekranli uretim akisinin mantigi (Mission Control 'Bugun' sekmesi kullanir).

Adimlar: 1) gundem adaylari  2) kaynak sayfa -> kanit adaylari  3) kanit secimi -> paket
         4) plan onizleme  5) private uretim  6) inceleme + (sadece sen) YAYINLA

Bu modul HICBIR korumayi gevsetmez: claim_lint / source_check / sensitivity_gate / gunluk sinir (daily_limit)
motorun icinde aynen calisir. Burada sadece (a) aday puanlama ve (b) paket hazirligi var.
Gundem puani "viral olur" tahmini DEGILDIR: kanalin kuralina (birincil belge + kendi odevini kendi notlayan
iddia) ne kadar uydugunu ve ne kadar taze oldugunu olcer; sonuc gecmisi _engine/bugun_gecmis.jsonl'e yazilir.
"""
import datetime
import email.utils
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import claim_lint
import daily_limit
import kaynak_cek

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
ADAY_YOL = os.path.join(ENGINE, "gundem_adaylari.json")
AKTIF_YOL = os.path.join(ENGINE, "bugun_aktif.json")
KAYNAK_ADAY_YOL = os.path.join(ENGINE, "kaynak_adaylar.json")
GECMIS_YOL = os.path.join(ENGINE, "bugun_gecmis.jsonl")

GDELT_QUERY = '(OpenAI OR Anthropic OR Nvidia OR "Google DeepMind" OR Mistral OR "Meta AI" OR xAI OR "Hugging Face" OR DeepSeek OR Gemini OR Claude) sourcelang:english'

# Kaynagi sirketin KENDI sayfasi / birincil belge olan alanlar (Receipt dogrudan sayfadan kurulur)
BIRINCIL = {"openai.com", "anthropic.com", "mistral.ai", "nvidia.com", "blogs.nvidia.com", "blog.google",
            "deepmind.google", "ai.meta.com", "about.fb.com", "microsoft.com", "blogs.microsoft.com", "x.ai",
            "huggingface.co", "arxiv.org", "sec.gov", "ai.google.dev", "aws.amazon.com", "cohere.com",
            "stability.ai", "perplexity.ai", "deepseek.com", "qwenlm.github.io"}

# Receipt'e uyan iddia kaliplari (sirketin kendi iddiasi)
IDDIA = ["state-of-the-art", "outperform", "beats ", "best ", "fastest", "most powerful", "record", "open-source",
         "open source", "open-weight", "safest", "first ", "breakthrough", "surpass", "leading", "claims"]
# Cikar catismasi / kendi odevini kendi notlayan: yalniz kucuk BONUS (operator karari 8 Ekim 2026; once birincil kriterdi)
CIKAR = ["own benchmark", "self-reported", "internal benchmark", "invests in", "funds ", "stake in", "acquires",
         "circular", "its own", "grades its own", "self-assessed"]


def _now():
    return datetime.datetime.now()


def _alan(url):
    try:
        h = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    return h[4:] if h.startswith("www.") else h


KURUM_ADI = {"allenai": "Ai2", "nvidia": "NVIDIA", "openai": "OpenAI", "mistral": "Mistral", "deepmind": "Google DeepMind",
             "aws": "AWS", "anthropic": "Anthropic", "huggingface": "Hugging Face", "microsoft": "Microsoft", "google": "Google",
             "meta": "Meta", "x": "xAI", "cohere": "Cohere", "deepseek": "DeepSeek"}


def kurum_tahmini(url):
    """Sayfanin GERCEK sahibi/yazari. Alan adi yaniltabilir: huggingface.co/blog/allenai/... Hugging Face'in degil Ai2'nin yazisidir
    (8 Ekim 2026: Konsey bunu Hugging Face'e atfetti). Yol 'blog/<kurum>/...' bicimindeyse kurum yoldan alinir."""
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return ""
    host = u.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    parts = [p for p in u.path.split("/") if p]
    if host.endswith("huggingface.co") and len(parts) >= 3 and parts[0] == "blog":
        ad = parts[1].lower()
    else:
        labels = host.split(".")
        ad = labels[-2] if len(labels) >= 2 else host
        if host.endswith("amazon.com") and labels[0] == "aws":
            ad = "aws"
    return KURUM_ADI.get(ad, ad[:1].upper() + ad[1:])


def birincil_mi(url):
    h = _alan(url)
    return any(h == d or h.endswith("." + d) for d in BIRINCIL)


def _yas_saat(seendate, now=None):
    """GDELT seendate: 20261008T143000Z"""
    now = now or datetime.datetime.utcnow()
    try:
        t = datetime.datetime.strptime(seendate[:15], "%Y%m%dT%H%M%S")
        return max((now - t).total_seconds() / 3600.0, 0.0)
    except Exception:
        return None


def puanla(makale, now=None):
    """Tek haber -> {puan, etiketler, engel}. Saf fonksiyon (test edilebilir)."""
    baslik = (makale.get("title") or "")
    low = baslik.lower()
    url = makale.get("url") or ""
    puan, et = 0, []
    if birincil_mi(url):
        puan += 4
        et.append("birincil kaynak")
    iddialar = [k for k in IDDIA if k in low]
    if iddialar:
        puan += min(len(iddialar), 2) * 2
        et.append("iddia: " + iddialar[0].strip())
    cikar = [k for k in CIKAR if k in low]
    if cikar:
        puan += 1                       # 8 Ekim 2026 operator karari: PRIORITY birincil kriter degil, yalniz BONUS
        et.append("cikar catismasi (bonus)")
    yas = _yas_saat(makale.get("seendate", ""), now)
    if yas is not None:
        if yas < 6:
            puan += 2
            et.append("taze (<6s)")
        elif yas < 24:
            puan += 1
    puan += min(makale.get("haber_sayisi", 1) - 1, 3)  # birden cok kaynak yazdiysa konu gercek
    engel = ""
    for k in claim_lint.lint(baslik):
        if k[0] in claim_lint.BLOCKING:
            engel = "baslik riskli ifade iceriyor: " + k[0]
            break
    return {"puan": puan, "etiketler": et, "engel": engel}


def _anahtar(baslik):
    return {w for w in re.findall(r"[a-z][a-z\-]{3,}", baslik.lower())} - {
        "with", "that", "this", "from", "have", "will", "your", "about", "after", "more", "than", "into", "says"}


def kumele(makaleler):
    """Ayni konuyu yazan haber sayisini hesapla (en az 3 ortak anlamli kelime)."""
    keys = [_anahtar(m.get("title", "")) for m in makaleler]
    for i, m in enumerate(makaleler):
        m["haber_sayisi"] = 1 + sum(1 for j in range(len(makaleler)) if j != i and len(keys[i] & keys[j]) >= 3)
    return makaleler


def sirala(makaleler, now=None, ilk=15):
    kumele(makaleler)
    out = []
    gorulen = set()
    for m in makaleler:
        url = m.get("url") or ""
        if not url or url in gorulen:
            continue
        gorulen.add(url)
        p = puanla(m, now)
        out.append({"title": m.get("title", ""), "url": url, "alan": _alan(url), "kurum": kurum_tahmini(url), "seendate": m.get("seendate", ""),
                    "haber_sayisi": m.get("haber_sayisi", 1), **p})
    out.sort(key=lambda x: (x["engel"] != "", -x["puan"]))
    return out[:ilk]


GDELT_YEDEK = "artificial intelligence sourcelang:english"
GDELT_ONBELLEK = os.path.join(ENGINE, "gdelt_onbellek.json")
GDELT_TAZE_DK = 30          # bu kadar dakika icinde basarili sonuc varsa GDELT'e hic sorma
GDELT_ESKI_SAAT = 6         # istek 429/hata verirse en fazla bu kadar eski onbellek kullanilir


def _onbellek_oku(en_fazla_dk):
    try:
        with open(GDELT_ONBELLEK, encoding="utf-8") as f:
            d = json.load(f)
        yas = (_now() - datetime.datetime.fromisoformat(d["zaman"])).total_seconds() / 60
        return d["articles"] if yas <= en_fazla_dk else None
    except Exception:
        return None


def _onbellek_yaz(articles):
    if not articles:          # bos sonucu ONBELLEGE YAZMA: gecici bir bosluk 30 dk boyunca haber indeksini yok etmesin
        return
    try:
        os.makedirs(ENGINE, exist_ok=True)
        with open(GDELT_ONBELLEK, "w", encoding="utf-8") as f:
            json.dump({"zaman": _now().isoformat(timespec="seconds"), "articles": articles}, f, ensure_ascii=True)
    except Exception:
        pass


def gdelt_cek(max_records=60, timeout=25):
    """429 (hiz siniri) -> 1 kez bekleyip tekrar; 400/uyumsuz sorgu -> yedek basit sorgu."""
    import time as _t
    taze = _onbellek_oku(GDELT_TAZE_DK)
    if taze is not None:
        return taze
    son_hata = None
    for q in (GDELT_QUERY, GDELT_YEDEK):
        for deneme in range(2):
            qs = urllib.parse.urlencode({"query": q, "mode": "ArtList", "maxrecords": str(max_records),
                                         "format": "json", "sort": "DateDesc", "timespan": "24h"})
            req = urllib.request.Request("https://api.gdeltproject.org/api/v2/doc/doc?" + qs, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    txt = r.read().decode("utf-8", errors="replace")
                try:
                    arts = json.loads(txt).get("articles", [])
                    if not arts:                      # bos cevap = sorgu/gecici sorun: siradaki (yedek) sorguyu dene
                        son_hata = RuntimeError("GDELT bos sonuc dondurdu")
                        break
                    _onbellek_yaz(arts)
                    return arts
                except ValueError:
                    son_hata = RuntimeError("GDELT JSON degil: " + txt[:80].replace("\n", " "))
                    break
            except urllib.error.HTTPError as e:
                son_hata = e
                if e.code == 429:
                    if deneme == 0:
                        _t.sleep(8)
                        continue
                    break
                break
            except Exception as e:
                son_hata = e
                break
    eski = _onbellek_oku(GDELT_ESKI_SAAT * 60)
    if eski is not None:                      # canli istek basarisiz: eski ama yakin sonucu kullan (haber yine kaynakli)
        return eski
    raise son_hata or RuntimeError("GDELT cevap vermedi")


# Sirketlerin KENDI yayin akislari (birincil kaynak: Receipt dogrudan bu sayfalardan kurulur).
# Adresler zamanla degisebilir: calismayan akis atlanir ve ekranda "okunamadi" diye raporlanir.
FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://deepmind.google/blog/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://blogs.nvidia.com/feed/",
    "https://huggingface.co/blog/feed.xml",
    "https://mistral.ai/rss.xml",
    "https://ai.meta.com/blog/rss/",
    "https://aws.amazon.com/blogs/machine-learning/feed/",
    "https://blogs.microsoft.com/ai/feed/",
]

# Konu uyumu: baslikta yapay zeka sirketi/modeli/olcutu gecmeyen haberler (enerji kurallari, yazilim duyurusu...) elenir
KONU = re.compile(r"\b(openai|anthropic|claude|chatgpt|gpt-?\d?|gemini|deepmind|mistral|llama|meta ai|nvidia|xai|grok|deepseek|qwen|"
                  r"hugging ?face|copilot|llm|large language model|language model|ai model|benchmark|open[- ]?(?:source|weight)|"
                  r"foundation model|chip|gpu|inference|agent|reasoning|safety|alignment)s?\b", re.I)


def konu_uyar(baslik):
    return bool(KONU.search(baslik or ""))


def _tarih_gdelt(s):
    """RSS (RFC822) veya Atom (ISO8601) tarihi -> GDELT bicimi (20261008T143000Z, UTC)."""
    if not s:
        return ""
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return ""
    if d.tzinfo is not None:
        d = d.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return d.strftime("%Y%m%dT%H%M%SZ")


def feed_parse(xml_text):
    """RSS 2.0 ve Atom -> [{title,url,seendate}]"""
    out = []
    root = ET.fromstring(xml_text)
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag == "item":
            t = (it.findtext("title") or "").strip()
            u = (it.findtext("link") or "").strip()
            d = it.findtext("pubDate") or ""
        elif tag == "entry":
            t = (next((e.text for e in it if e.tag.split("}")[-1] == "title"), "") or "").strip()
            u = ""
            for e in it:
                if e.tag.split("}")[-1] == "link":
                    u = e.get("href") or (e.text or "")
                    if e.get("rel") in (None, "alternate"):
                        break
            d = next((e.text for e in it if e.tag.split("}")[-1] in ("updated", "published")), "") or ""
        else:
            continue
        if t and u.startswith("http"):
            out.append({"title": t, "url": u.strip(), "seendate": _tarih_gdelt(d)})
    return out


def feed_cek(url, timeout=15, maks=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        txt = r.read().decode("utf-8", errors="replace")
    return feed_parse(txt)[:maks]


def gundem_yenile():
    """GDELT + sirket akislarini ceker, konu uyumuna gore suzer, puanlar, _engine/gundem_adaylari.json'a yazar."""
    ham, rapor = [], []
    try:
        g = gdelt_cek()
        ham += g
        rapor.append(f"haber indeksi: {len(g)}")
    except Exception as e:
        kod = getattr(e, "code", "")
        rapor.append(f"haber indeksi OKUNAMADI ({type(e).__name__}{' ' + str(kod) if kod else ''}: {str(e)[:60]})")
    ok, kotu = 0, []
    for f in FEEDS:
        try:
            ham += feed_cek(f)
            ok += 1
        except Exception:
            kotu.append(_alan(f))
    rapor.append(f"sirket akislari: {ok}/{len(FEEDS)} okundu" + (f" (okunamayan: {', '.join(kotu)})" if kotu else ""))
    if not ham:
        return "[HATA] Hicbir kaynaktan haber alinamadi. " + "; ".join(rapor) + ". Biraz sonra tekrar dene veya adresi elle yapistir."
    uygun = [m for m in ham if konu_uyar(m.get("title", ""))]
    adaylar = sirala(uygun)
    os.makedirs(ENGINE, exist_ok=True)
    with open(ADAY_YOL, "w", encoding="utf-8") as f:
        json.dump({"zaman": _now().isoformat(timespec="seconds"), "adaylar": adaylar, "ham_sayi": len(ham),
                   "uygun_sayi": len(uygun), "rapor": rapor}, f, ensure_ascii=True, indent=1)
    return f"{len(ham)} haber tarandi, {len(uygun)} konuya uygun, {len(adaylar)} aday. ({'; '.join(rapor)})"


def gundem_oku():
    try:
        with open(ADAY_YOL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"zaman": None, "adaylar": [], "ham_sayi": 0}


# ----------------------------------------------------------------------------- kaynak / paket
def kaynak_analiz(url, claim_key="state-of-the-art", keys=None, html=None):
    """Sayfayi KODLA cek, kanit adaylarini numarala. Adaylar KAYNAK_ADAY_YOL'a yazilir (secim ayni goruntuye uygulanir)."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        return {"ok": False, "error": "Adres http:// veya https:// ile baslamali."}
    try:
        if html is None:
            html = kaynak_cek.fetch(url)
    except Exception as e:
        return {"ok": False, "error": f"Sayfa alinamadi: {type(e).__name__}: {e}"}
    title, lines = kaynak_cek.parse_html(html)
    sents = kaynak_cek.split_sentences(lines)
    if len(sents) < 15:
        return {"ok": False, "error": "Sayfa metni cok kisa (JavaScript ile yukleniyor olabilir). Sayfayi Ctrl+S ile "
                                      "'Yalnizca HTML' kaydedip komut satirindan kaynak_cek.py --file ile dene."}
    keys = keys or kaynak_cek.DEFAULT_KEYS
    sk = [(kaynak_cek.score(s, keys), i, s) for i, s in enumerate(sents)]
    cands = sorted([(sc, i, s) for sc, i, s in sk if sc[0] > 0], key=lambda x: (-x[0][0], x[1]))[:40]
    claim = next((s for s in sents if claim_key.lower() in s.lower()), "")
    veri = {"url": url, "title": title, "claim_key": claim_key, "keys": keys,
            "fetched_at": _now().isoformat(timespec="seconds"), "claim": claim, "sentences": sents,
            "adaylar": [{"no": n, "idx": i, "kelimeler": sc[1], "metin": s} for n, (sc, i, s) in enumerate(cands, 1)],
            "onerilen": list(range(1, min(len(cands), 6) + 1))}
    os.makedirs(ENGINE, exist_ok=True)
    with open(KAYNAK_ADAY_YOL, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=True, indent=1)
    return {"ok": True, "title": title, "claim": claim, "adaylar": veri["adaylar"], "onerilen": veri["onerilen"],
            "cumle_sayisi": len(sents), "birincil": birincil_mi(url)}


def kaynak_paketle(secim, facts=None):
    """Kullanicinin sectigi numaralardan paket olusturur (kaynak_cek.build_packet ile AYNI kod yolu)."""
    try:
        with open(KAYNAK_ADAY_YOL, encoding="utf-8") as f:
            v = json.load(f)
    except Exception:
        return {"ok": False, "error": "Once kaynak sayfasini cek (Adim 2)."}
    no = {a["no"]: a for a in v["adaylar"]}
    secili = [int(x) for x in secim if int(x) in no]
    if not secili:
        return {"ok": False, "error": "En az bir kanit cumlesi sec."}
    idx = [no[n]["idx"] for n in secili]
    facts = [kaynak_cek.ascii_norm(f.strip()) for f in (facts or []) if f.strip()]
    pk = kaynak_cek.build_packet(v["url"], v["title"], v["sentences"], v["claim_key"], v["keys"], idx, facts,
                                 v["fetched_at"])
    stamp = _now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(ENGINE, f"kaynak_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pk, f, ensure_ascii=True, indent=1)
    with open(os.path.join(ENGINE, "kaynak_son.txt"), "w", encoding="utf-8") as f:
        f.write(path)
    aktif_yaz(path, False)
    # konu satirindaki iddia cumlesi sayfanin KENDI sozudur (Receipt'te dogrulanmis alinti olarak kullanilir): taramaya alinmaz
    _konu = pk["topic"].replace(pk["claim"], " ") if pk.get("claim") else pk["topic"]
    uyarilar = [f"{k[0]}: {', '.join(k[1])}" for k in claim_lint.lint(_konu)]
    gecmis_yaz({"olay": "paket", "url": v["url"], "baslik": v["title"], "kanit": len(pk["evidence"]),
                "iddia": bool(pk["claim"]), "paket": path})
    return {"ok": True, "paket": path, "topic": pk["topic"], "kanit": len(pk["evidence"]),
            "iddia": pk["claim"], "uyarilar": uyarilar}


# ----------------------------------------------------------------------------- durum / yardimcilar
def receipt_listesi():
    d = os.path.join(HERE, "receipts")
    try:
        return sorted(f for f in os.listdir(d) if f.endswith(".json"))
    except Exception:
        return []


def bugun_durum(gun=None):
    gun = gun or _now().strftime("%Y-%m-%d")
    kayit = os.path.join(ENGINE, gun, ".uploaded_today.json")
    info = daily_limit.read_info(kayit)
    return {"gun": gun, "adet": info.get("count", 0), "limit": daily_limit.MAX_DAILY,
            "videolar": info.get("videos", []), "video_id": info.get("video_id"),
            "review_mode": os.path.exists(os.path.join(HERE, "REVIEW_MODE")),
            "paket": _son_paket()}


def _aktif():
    try:
        with open(AKTIF_YOL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def aktif_yaz(paket, kullanildi=False):
    os.makedirs(os.path.dirname(AKTIF_YOL), exist_ok=True)
    with open(AKTIF_YOL, "w", encoding="utf-8") as f:
        json.dump({"paket": paket, "kullanildi": kullanildi, "zaman": _now().isoformat(timespec="seconds")}, f)


def _son_paket(kullanilmis=False):
    """YALNIZ bu ekranda hazirlanan, henuz uretilmemis paket. Eski kaynak_son.txt (onceki gunlerin/CLI'nin paketi) KULLANILMAZ:
    yoksa konu secmeden 'Uret'e basinca ayni video ikinci kez uretilirdi. kullanilmis=True: Paylas adimi icin son paketi de ver."""
    a = _aktif()
    p = a.get("paket", "")
    if not p or not os.path.exists(p):
        return ""
    if a.get("kullanildi") and not kullanilmis:
        return ""
    return p


def paket_kullanildi():
    a = _aktif()
    if a.get("paket"):
        aktif_yaz(a["paket"], True)


def gecmis_yaz(kayit):
    kayit = dict(kayit)
    kayit["zaman"] = _now().isoformat(timespec="seconds")
    try:
        os.makedirs(ENGINE, exist_ok=True)
        with open(GECMIS_YOL, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=True) + "\n")
    except Exception:
        pass


YAYIN_KONTROL = [
    "Motorun [source_check] satiri TEMIZ (degilse video zaten private kalir)",
    "Metindeki her alinti kaynak sayfadaki cumlelerle birebir ayni",
    "Niyet atfi yok (gizlice / orttu / tuzak / kasten)",
    "Kaynaksiz rakam veya ucuncu sirket adi yok",
    "Baslik nesnel; soru-ima degil",
]


def yayin_dogrula(onay, isaretli):
    """YAYINLA yazisi birebir + butun kontrol maddeleri isaretli olmali."""
    if onay != "YAYINLA":
        return "Onay icin tam olarak YAYINLA yaz."
    if int(isaretli or 0) < len(YAYIN_KONTROL):
        return "Kontrol listesindeki tum maddeleri isaretle."
    return ""


# ----------------------------------------------------------------------------- sosyal paylasim taslaklari
PLATFORMLAR = {
    "reddit": "Reddit (konu tartismasi; videoyu ilk yorumda paylas)",
    "x": "X / Twitter",
}


def _kisalt(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def paylasim_taslak(platform, paket, video_id):
    """Kurala uygun, kaynakli, nesnel metin. Niyet atfi/kesin hukum yok; iddia sayfadan alintidir.
    Otomatik GONDERILMEZ: operator kopyalar ve kendi paylasir."""
    if platform not in PLATFORMLAR:
        return {"ok": False, "error": "Bilinmeyen platform."}
    baslik = _kisalt(paket.get("title", ""), 90)
    claim = _kisalt(paket.get("claim", ""), 160)
    url = paket.get("url", "")
    video = f"https://youtu.be/{video_id}" if video_id else "(video linki)"
    if platform == "reddit":
        t = {"baslik": f"{baslik}: what the page itself says vs. what it shows",
             "govde": (f"The page states: \"{claim}\"\n\n" if claim else "") +
                      f"I read the primary page line by line and quoted only what is on it. Source: {url}\n\n"
                      "What do you think the page does and does not support?",
             "ilk_yorum": f"I turned the comparison into a 25-second video with the quotes on screen: {video}",
             "not": "Kurallar: her subreddit'in kendi tanitim kuralini oku; once tartisma olarak gonder, videoyu ilk yorumda ver; "
                    "baska konulara da katki yap (yalnizca kendi linkini paylasan hesap spam sayilir)."}
    else:
        t = {"baslik": "", "govde": (f"{baslik}\n\n" + (f"Page says: \"{_kisalt(claim, 120)}\"\n" if claim else "") +
                                     f"Source: {url}\nVideo: {video}"),
             "ilk_yorum": "", "not": "280 karakteri asarsa kaynak ve video linkini ikinci tweet'e tasi."}
    uyari = []
    for alan in ("baslik", "govde", "ilk_yorum"):
        for k in claim_lint.lint(t[alan]):
            if k[0] in claim_lint.BLOCKING:
                uyari.append(f"{alan}: {k[0]} ({', '.join(k[1])})")
    t.update(ok=True, platform=platform, uyari=uyari)
    return t


def paylasim_kaydet(platform, video_id):
    gecmis_yaz({"olay": "paylasim", "platform": platform, "video_id": video_id})
    return {"ok": True}


# ----------------------------------------------------------------------------- sayfa hazirlik (KODLA; Konsey'den once)
IDDIA_ANAHTARLAR = ["state-of-the-art", "outperform", "best-in-class", "industry-leading", "most powerful", "fastest",
                    "surpass", "open-source", "open source", "open-weight", "open weight", "breakthrough", "leading",
                    "maximize", "maximise", "lowest", "highest", "best ", "unmatched", "record", "world's first", "most efficient"]
# sayi + kiyas: "up to 10x faster", "40% lower cost", "2x more efficient"
KIYAS = re.compile(r"\b(?:up to |over |nearly |more than )?\d+(?:\.\d+)?\s?(?:x|×|%|percent|-fold)\s+(?:\w+\s+){0,2}"
                   r"(?:faster|slower|lower|higher|better|cheaper|more|less|fewer|greater|improvement|reduction|increase)", re.I)
MIN_KANIT = 3


def _norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _baslik_mi(cumle, baslik):
    """Sayfanin kendi basligi/basligin tekrari iddia degildir."""
    a, b = _norm(cumle), _norm(baslik)
    if not a or not b:
        return False
    return a == b or a in b or (b in a and len(a) - len(b) < 25)


def sayfa_hazirlik(url, html=None):
    """Adayin sayfasini kodla oku: GOVDEDE sirketin kendi iddiasi (baslik degil) + kanit adaylari var mi?
    Donus: {ok, iddia, iddia_anahtar, kanit, hata}. ok = iddia VAR ve kanit >= MIN_KANIT.
    iddia_anahtar: kaynak_cek'e verilecek alt-dize (o cumlede aynen gecer)."""
    try:
        if html is None:
            html = kaynak_cek.fetch(url)
        title, lines = kaynak_cek.parse_html(html)
        sents = kaynak_cek.split_sentences(lines)
    except Exception as e:
        return {"ok": False, "iddia": "", "iddia_anahtar": "", "kanit": 0, "hata": f"sayfa okunamadi ({type(e).__name__})"}
    if len(sents) < 15:
        return {"ok": False, "iddia": "", "iddia_anahtar": "", "kanit": 0, "hata": "sayfa metni cok kisa (JavaScript ile yukleniyor olabilir)"}
    govde = [x for x in sents if len(x) >= 40 and not _baslik_mi(x, title)]
    iddia, anahtar = "", ""
    for x in govde:                              # once sayi+kiyas ("up to 10x faster"), sonra anahtar sozcuk
        m = KIYAS.search(x)
        if m:
            iddia, anahtar = x, m.group(0).lower()
            break
    if not iddia:
        for k in IDDIA_ANAHTARLAR:
            c = next((x for x in govde if k in x.lower()), "")
            if c:
                iddia, anahtar = c, k
                break
    kanit = sum(1 for x in sents if x != iddia and not _baslik_mi(x, title) and kaynak_cek.score(x, kaynak_cek.DEFAULT_KEYS)[0] > 0)
    hata = "" if iddia else "govdede sirketin kendi iddiasi (state-of-the-art, 10x faster, maximize...) bulunamadi"
    if iddia and kanit < MIN_KANIT:
        hata = f"kanit cumlesi yetersiz ({kanit})"
    return {"ok": bool(iddia) and kanit >= MIN_KANIT, "iddia": iddia[:300], "iddia_anahtar": anahtar, "kanit": kanit, "hata": hata}
