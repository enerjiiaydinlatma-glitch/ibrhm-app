"""BUGUN - tek ekranli uretim akisinin mantigi (Mission Control 'Bugun' sekmesi kullanir).

Adimlar: 1) gundem adaylari  2) kaynak sayfa -> kanit adaylari  3) kanit secimi -> paket
         4) plan onizleme  5) private uretim  6) inceleme + (sadece sen) YAYINLA

Bu modul HICBIR korumayi gevsetmez: claim_lint / source_check / sensitivity_gate / gunluk sinir (daily_limit)
motorun icinde aynen calisir. Burada sadece (a) aday puanlama ve (b) paket hazirligi var.
Gundem puani "viral olur" tahmini DEGILDIR: kanalin kuralina (birincil belge + kendi odevini kendi notlayan
iddia) ne kadar uydugunu ve ne kadar taze oldugunu olcer; sonuc gecmisi _engine/bugun_gecmis.jsonl'e yazilir.
"""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request

import claim_lint
import daily_limit
import kaynak_cek

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
ADAY_YOL = os.path.join(ENGINE, "gundem_adaylari.json")
KAYNAK_ADAY_YOL = os.path.join(ENGINE, "kaynak_adaylar.json")
GECMIS_YOL = os.path.join(ENGINE, "bugun_gecmis.jsonl")

GDELT_QUERY = '(OpenAI OR Anthropic OR Nvidia OR "Google DeepMind" OR Mistral OR Meta AI OR xAI OR "Hugging Face" OR "AI model") sourcelang:english'

# Kaynagi sirketin KENDI sayfasi / birincil belge olan alanlar (Receipt dogrudan sayfadan kurulur)
BIRINCIL = {"openai.com", "anthropic.com", "mistral.ai", "nvidia.com", "blogs.nvidia.com", "blog.google",
            "deepmind.google", "ai.meta.com", "about.fb.com", "microsoft.com", "blogs.microsoft.com", "x.ai",
            "huggingface.co", "arxiv.org", "sec.gov", "ai.google.dev", "aws.amazon.com", "cohere.com",
            "stability.ai", "perplexity.ai", "deepseek.com", "qwenlm.github.io"}

# Receipt'e uyan iddia kaliplari (sirketin kendi iddiasi)
IDDIA = ["state-of-the-art", "outperform", "beats ", "best ", "fastest", "most powerful", "record", "open-source",
         "open source", "open-weight", "safest", "first ", "breakthrough", "surpass", "leading", "claims"]
# PRIORITY (operator_rules.md): cikar catismasi / kendi odevini kendi notlayan
CIKAR = ["own benchmark", "self-reported", "invests", "investment", "funds", "funding", "stake", "partnership",
         "acquires", "acquisition", "revenue", "valuation", "circular", "its own", "internal", "evaluation"]


def _now():
    return datetime.datetime.now()


def _alan(url):
    try:
        h = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    return h[4:] if h.startswith("www.") else h


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
        puan += 3
        et.append("cikar catismasi (PRIORITY)")
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
        out.append({"title": m.get("title", ""), "url": url, "alan": _alan(url), "seendate": m.get("seendate", ""),
                    "haber_sayisi": m.get("haber_sayisi", 1), **p})
    out.sort(key=lambda x: (x["engel"] != "", -x["puan"]))
    return out[:ilk]


def gdelt_cek(max_records=60, timeout=25):
    qs = urllib.parse.urlencode({"query": GDELT_QUERY, "mode": "ArtList", "maxrecords": str(max_records),
                                 "format": "json", "sort": "DateDesc", "timespan": "24h"})
    req = urllib.request.Request("https://api.gdeltproject.org/api/v2/doc/doc?" + qs,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    return data.get("articles", [])


def gundem_yenile():
    """Adaylari ceker, puanlar, _engine/gundem_adaylari.json'a yazar. Donus: ozet metin."""
    try:
        ham = gdelt_cek()
    except Exception as e:
        return f"[HATA] Haber indeksi alinamadi ({type(e).__name__}: {e}). Biraz sonra tekrar dene veya adresi elle yapistir."
    adaylar = sirala(ham)
    os.makedirs(ENGINE, exist_ok=True)
    with open(ADAY_YOL, "w", encoding="utf-8") as f:
        json.dump({"zaman": _now().isoformat(timespec="seconds"), "adaylar": adaylar, "ham_sayi": len(ham)},
                  f, ensure_ascii=True, indent=1)
    return f"{len(ham)} haber tarandi, {len(adaylar)} aday listelendi."


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
    uyarilar = [f"{k[0]}: {', '.join(k[1])}" for k in claim_lint.lint(pk["topic"])]
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


def _son_paket():
    try:
        with open(os.path.join(ENGINE, "kaynak_son.txt"), encoding="utf-8") as f:
            p = f.read().strip()
        return p if os.path.exists(p) else ""
    except Exception:
        return ""


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
