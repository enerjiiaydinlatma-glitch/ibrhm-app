"""GUNUN ANALIZI - konu analizi -> veri analizi -> cikti toplama -> Konsey tartismasi -> karar.

Siralama (operator karari): 1) konulari analiz et  2) kanal verisini analiz et  3) ciktilari topla
4) Konsey tartissin  5) konu belirlensin. Paylasimdan HEMEN ONCE calisir (onceden hazirlik yok).

Guvenlik (degismez):
- Konsey yalniz KAYNAGI OLAN adaylar arasindan secer; olgu/rakam/URL uretemez. Secim aday listesinde
  yoksa reddedilir ve kural tabanli siralamaya dusulur.
- Kaynak ve alintilar yine KODLA cekilir (kaynak_cek), dogrulama motorda (source_check/claim_lint).
- Konu onayi (ve yayin onayi) ilk asamada insandadir; 'guven' olcutu _engine/bugun_gecmis.jsonl'den hesaplanir.
"""
import datetime
import json
import os
import re
import statistics

import sutun as sutun_mod

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
SON_YOL = os.path.join(ENGINE, "analiz_son.json")
GECMIS_YOL = os.path.join(ENGINE, "bugun_gecmis.jsonl")
GIRIS_YOL = os.path.join(ENGINE, "guven_giris.json")

RETENTION_TABAN = 15.5       # % (28 gun tabani, analysis/2026-10-07_pilot_plani.md)
ONAY_ESIGI = 0.70            # onerilerin en az bu orani degismeden onaylanmali
GUVEN_GUN = 7                # operator karari: 7 gun, ayni uc sart

# ----------------------------------------------------------------------------- veri analizi
def kanal_videolari(max_sonuc=25):
    """YouTube Data API (mevcut OAuth). Hata olursa bos liste + neden doner."""
    try:
        from googleapiclient.discovery import build
        from youtube_auth import get_credentials
        yt = build("youtube", "v3", credentials=get_credentials())
        ch = yt.channels().list(part="statistics,contentDetails", mine=True).execute()["items"][0]
        up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        ids = [i["contentDetails"]["videoId"] for i in
               yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=max_sonuc).execute()["items"]]
        vids = yt.videos().list(part="snippet,statistics,status", id=",".join(ids)).execute()["items"]
        out = []
        for v in vids:
            st, sn = v.get("statistics", {}), v["snippet"]
            out.append({"id": v["id"], "title": sn["title"], "published": sn["publishedAt"],
                        "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                        "comments": int(st.get("commentCount", 0)),
                        "privacy": v.get("status", {}).get("privacyStatus", "")})
        return {"ok": True, "abone": int(ch["statistics"].get("subscriberCount", 0)), "videolar": out}
    except Exception as e:
        return {"ok": False, "hata": f"{type(e).__name__}: {e}", "abone": None, "videolar": []}


def _sablon(baslik):
    """Baslik kalibi: ':' oncesi, yoksa ilk iki kelime."""
    b = (baslik or "").strip()
    if ":" in b[:40]:
        return b.split(":", 1)[0].strip().lower()
    return " ".join(b.lower().split()[:2])


def kalip_sinyalleri(videolar):
    """Az veriyle tek tek video yorumlamak gurultudur: KALIP duzeyinde ozet (baslik sablonu, saat, egilim)."""
    pub = [v for v in videolar if v.get("privacy", "public") == "public"]
    if not pub:
        return {"video_sayisi": 0}
    views = [v["views"] for v in pub]
    sirali = sorted(pub, key=lambda v: v["published"], reverse=True)
    son5 = [v["views"] for v in sirali[:5]]
    onceki5 = [v["views"] for v in sirali[5:10]]
    gruplar = {}
    for v in pub:
        gruplar.setdefault(_sablon(v["title"]), []).append(v["views"])
    sablon = sorted(({"sablon": k, "adet": len(x), "ortalama": round(sum(x) / len(x), 1)} for k, x in gruplar.items()),
                    key=lambda r: -r["adet"])[:6]
    saat = {}
    for v in pub:
        try:
            h = int(v["published"][11:13])
        except Exception:
            continue
        saat.setdefault(h, []).append(v["views"])
    # Tek bir saat kovasi bilgi tasimaz: tracker yalniz TARIH tutar ve ogrenme.kanal_tracker her videoya
    # T12:00:00Z yazar (uydurma saat). Bu durumda saat sinyali Konsey'e GIDEREK YANILTMASIN diye verilmez.
    saat_ort = []
    if len(saat) >= 2:
        saat_ort = sorted(({"saat_utc": h, "adet": len(x), "ortalama": round(sum(x) / len(x), 1)} for h, x in saat.items()),
                          key=lambda r: -r["ortalama"])[:4]
    en_iyi = sorted(pub, key=lambda v: -v["views"])[:3]
    en_kotu = sorted(pub, key=lambda v: v["views"])[:3]
    return {"video_sayisi": len(pub), "medyan_izlenme": statistics.median(views), "ortalama_izlenme": round(sum(views) / len(views), 1),
            "son5_ortalama": round(sum(son5) / len(son5), 1) if son5 else None,
            "onceki5_ortalama": round(sum(onceki5) / len(onceki5), 1) if onceki5 else None,
            "baslik_sablonlari": sablon, "saatler": saat_ort,
            "saat_notu": "" if saat_ort else "Yayin saati verisi yok (kaynakta yalniz tarih var) - saat yorumu yapma.",
            "en_iyi": [{"baslik": v["title"][:90], "izlenme": v["views"]} for v in en_iyi],
            "en_kotu": [{"baslik": v["title"][:90], "izlenme": v["views"]} for v in en_kotu],
            "uyari": "Ornek az (medyan izlenme dusuk): bunlar yon gostergesidir, kanit degil."}


def veri_ozeti(kanal=None, rapor=None):
    kanal = kanal if kanal is not None else kanal_videolari()
    o = {"kanal_ok": kanal.get("ok", False), "abone": kanal.get("abone"),
         "taban": {"izlemeye_devam_yuzde": RETENTION_TABAN},
         "sinyaller": kalip_sinyalleri(kanal.get("videolar", []))}
    if not kanal.get("ok"):
        o["kanal_hata"] = kanal.get("hata")
    if rapor:
        try:
            o["analytics_raporu"] = json.dumps(rapor, ensure_ascii=False)[:2500]
        except Exception:
            pass
    return o


# ----------------------------------------------------------------------------- adaylar ve brifing
def aday_kimlikleri(adaylar, en_fazla=8):
    """Engelli adaylar tartismaya HIC girmez. Kimlik: A1, A2, ..."""
    ok = [a for a in adaylar if not a.get("engel")][:en_fazla]
    return [{**a, "id": f"A{i}"} for i, a in enumerate(ok, 1)]


def brifing(adaylar, veri):
    satir = []
    for a in adaylar:
        h = a.get("hazir") or {}
        satir.append(f"{a['id']}: {a['title']} | kaynak: {a.get('alan','?')} | SAYFANIN GERCEK SAHIBI/YAZARI (iddiayi bu kurumdan bilmelisin, alan adindan degil): {a.get('kurum') or '?'} | puan {a['puan']} | "
                     f"{a.get('haber_sayisi',1)} haber | etiket: {', '.join(a.get('etiketler') or []) or '-'}"
                     + (f" | SAYFADA IDDIA (kodla okundu): \"{h.get('iddia','')[:200]}\" | kanit cumlesi: {h.get('kanit', 0)}" if h else ""))
    return ("GUNUN ANALIZI. Kanal: Sign Council (YouTube Shorts, Ingilizce anlatim, 'Receipt' formati: tek iddia, tek birincil belge, "
            "dogrudan alintilar, hukum damgasi). Hedef: abone ve izlemeye devam oranini artirmak. "
            "ONEMLI: 'SAYFADA IDDIA' alani sayfanin KODLA okunmus gercek cumlesidir; gerekceni yalnizca bu cumleye ve verilere dayandir, "
            "basliktan tahmin yurutme. KURALLAR: yalnizca asagidaki adaylar arasindan sec; aday disinda konu, rakam veya baglanti UYDURMA; niyet atfi/suc dili yok. "
            "Oncelik: IZLEYICI ILGISI ve belgeyle sinanabilirlik. Sirketin kendi iddiasini kendi olcutuyle notlamasi (cikar catismasi) "
            "yalnizca kucuk bir BONUSTUR, secimin ana nedeni olamaz.\n\n"
            "ADAYLAR:\n" + "\n".join(satir) + "\n\nKANAL VERISI (ozet; ornek az, kesin hukum verme):\n" +
            json.dumps(veri, ensure_ascii=False)[:3500])


TUR_PLANI = [
    {"speaker": "alpha", "directive": "Kanal verisine (sutun sonuclari, baslik sablonlari, saatler, egilim) ve aday puanlarina bak; hangi 2 aday izleyicinin en cok ilgisini cekecek kalibina en yakin? "
     "Yalnizca brifingdeki sayilari kullan, yeni rakam uydurma. Verinin az oldugunu unutma. 3-5 cumle."},
    {"speaker": "beta", "directive": "Adaylari ELE: hangisi hukuki/itibar riski tasiyor (niyet atfi, suc dili, kaynaksiz rakam), hangisinin kaynagi zayif? "
     "Her elediginin kimligini (A1...) yaz. 3-5 cumle."},
    {"speaker": "gamma", "directive": "Izleyici acisindan: hangi aday sade bir dille anlatilabilir, merak uyandirir ve belgeyle sinanabilir? Yaniltma riski var mi? "
     "(Cikar catismasi varsa yalnizca ek bonus.) 3-5 cumle."},
    {"speaker": "delta", "directive": "Uc gorusun ortak noktasini bul ve adaylari 1-3 sirala (kimlikleriyle). 3-4 cumle."},
    {"speaker": "aura", "directive": "KARAR ver. Cevabin YALNIZCA su JSON olsun, baska hicbir sey yazma: "
     '{"secim":"A?","alternatif":["A?","A?"],"gerekce":"2 cumle Turkce, veriye dayali","aci":"videonun 1 cumlelik nesnel acisi"} '
     "'secim' brifingdeki bir kimlik olmak ZORUNDA."},
]


def karar_ayikla(metin, adaylar):
    """Aura'nin JSON'unu dogrula. Gecersiz/uydurma kimlik -> None."""
    ids = {a["id"] for a in adaylar}
    m = re.search(r"\{.*\}", metin or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    sec = str(d.get("secim", "")).strip().upper()
    if sec not in ids:
        return None
    alt = [str(x).strip().upper() for x in (d.get("alternatif") or []) if str(x).strip().upper() in ids and str(x).strip().upper() != sec]
    return {"secim": sec, "alternatif": alt[:2], "gerekce": str(d.get("gerekce", ""))[:500], "aci": str(d.get("aci", ""))[:300]}


def karar_ver(transcript, adaylar):
    son = next((t["text"] for t in reversed(transcript) if t.get("speaker") == "aura"), "")
    k = karar_ayikla(son, adaylar)
    if k:
        k["kaynak"] = "konsey"
        return k
    if not adaylar:
        return {"secim": None, "alternatif": [], "gerekce": "Uygun aday yok.", "aci": "", "kaynak": "yok"}
    return {"secim": adaylar[0]["id"], "alternatif": [a["id"] for a in adaylar[1:3]],
            "gerekce": "Konsey gecerli bir secim uretmedi; kural tabanli puan siralamasi kullanildi.", "aci": "", "kaynak": "kural"}


# ----------------------------------------------------------------------------- akis
def _yaz(durum):
    os.makedirs(ENGINE, exist_ok=True)
    with open(SON_YOL, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=True, indent=1)


def son():
    try:
        with open(SON_YOL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def sayfalari_kontrol(adaylar, hazirlik, en_fazla=6):
    """Her adayin sayfasini PARALEL oku. Iddia/kanit yoksa elenir. Donus: (uygunlar, elenenler)."""
    from concurrent.futures import ThreadPoolExecutor
    def _k(a):
        try:
            return hazirlik(a["url"])
        except Exception as e:
            return {"ok": False, "iddia": "", "iddia_anahtar": "", "kanit": 0, "hata": f"{type(e).__name__}"}
    with ThreadPoolExecutor(max_workers=en_fazla) as ex:
        sonuc = list(ex.map(_k, adaylar))
    uygun, elenen = [], []
    for a, h in zip(adaylar, sonuc):
        (uygun if h.get("ok") else elenen).append({**a, "hazir": h})
    return [{**a, "id": f"A{i}"} for i, a in enumerate(uygun, 1)], elenen


def calistir(gundem_yenile, gundem_oku, tartis, kanal=None, rapor=None, hazirlik=None, sutun=None):
    """gundem_yenile()/gundem_oku(): bugun.py; tartis(brifing, plan)->transcript: Mission Control'un Konsey calistiricisi.
    hazirlik(url): sayfa kodla okunur (bugun.sayfa_hazirlik); iddia/kanit yoksa aday Konsey'e HIC gitmez."""
    d = {"basladi": datetime.datetime.now().isoformat(timespec="seconds"), "adim": "veri", "durum": "calisiyor"}
    _yaz(d)
    # 1) kanal verisi + SUTUN karari (hizli; haber taramasi yalniz receipt sutununda yapilir)
    kv = kanal if kanal is not None else kanal_videolari()
    d["veri"] = veri_ozeti(kv, rapor)
    tablo = sutun_mod.istatistik(kv.get("videolar", []))
    d["sutunlar"] = sutun_mod.satirlar(tablo)
    d["sutun_oneri"] = sutun_mod.oner(tablo)
    d["sutun"] = sutun or d["sutun_oneri"]["sutun"]
    d["veri"]["sutun_sonuclari"] = [{k: r[k] for k in ("ad", "deneme", "ort_izlenme", "ort_yorum")} for r in d["sutunlar"] if r["deneme"]]
    if d["sutun"] != "receipt":
        d.update(adim="bitti", durum="sutun_hazir", bitti=datetime.datetime.now().isoformat(timespec="seconds"))
        _yaz(d)
        log({"olay": "oneri", "secim": d["sutun"], "tur": "sutun", "kaynak": d["sutun_oneri"]["mod"]})
        return f"Sutun onerisi: {sutun_mod.SUTUNLAR[d['sutun']]['ad']} ({d['sutun_oneri']['mod']})"
    # 2) receipt sutunu: haber adaylari -> sayfa kontrolu -> Konsey
    d["adim"] = "konu"
    _yaz(d)
    d["gundem_mesaj"] = gundem_yenile()
    adaylar = aday_kimlikleri(gundem_oku().get("adaylar", []))
    if hazirlik and adaylar:
        d["adim"] = "sayfa"
        _yaz(d)
        adaylar, d["elenen"] = sayfalari_kontrol(adaylar, hazirlik)
    d["adaylar"] = adaylar
    if not adaylar:
        d.update(adim="bitti", durum="aday_yok", karar=karar_ver([], []), veri=d["veri"])
        _yaz(d)
        return "Uygun aday bulunamadi."
    if len(adaylar) == 1:
        # tek aday: tartisacak secenek yok. Konsey'i calistirip sahte bir "secim" gerekcesi uretmeyiz; durumu acikca soyleriz.
        d["transcript"] = []
        d["karar"] = {"secim": adaylar[0]["id"], "alternatif": [], "aci": "", "kaynak": "tek-aday",
                      "gerekce": "Sayfa kontrolunu (iddia + kanit) gecen TEK aday bu; Konsey tartismasi yapilmadi. Konunun kanalimiza uygun olup olmadigina sen karar ver."}
    else:
        d["adim"] = "tartisma"
        _yaz(d)
        try:
            tr = tartis(brifing(adaylar, d["veri"]), TUR_PLANI)
        except Exception as e:
            tr = []
            d["tartisma_hata"] = f"{type(e).__name__}: {e}"
        d["transcript"] = tr
        d["karar"] = karar_ver(tr, adaylar)
    d.update(adim="bitti", durum="onay_bekliyor", bitti=datetime.datetime.now().isoformat(timespec="seconds"))
    _yaz(d)
    log({"olay": "oneri", "secim": d["karar"]["secim"], "kaynak": d["karar"]["kaynak"]})
    return f"Konu onerisi hazir: {d['karar']['secim']} ({d['karar']['kaynak']})"


def sutun_onayla(secim):
    """Operator sutunu onayladi. Onerilenden farkliysa 'degisti' (guven olcutu)."""
    if secim not in sutun_mod.SUTUNLAR:
        return {"ok": False, "error": "Bilinmeyen sutun."}
    d = son() or {}
    ilk = (d.get("sutun_oneri") or {}).get("sutun")
    log({"olay": "onay", "secim": secim, "tur": "sutun", "degisti": secim != ilk})
    d["sutun_onay"] = {"secim": secim, "degisti": secim != ilk}
    _yaz(d)
    return {"ok": True, "sutun": secim}


def aday_bul(secim):
    d = son() or {}
    return next((a for a in d.get("adaylar", []) if a["id"] == secim), None)


def onayla(secim):
    """Operator onayi. Konseyin ilk onerisinden farkliysa 'degisti' isaretlenir (guven olcutu)."""
    d = son() or {}
    a = aday_bul(secim)
    if not a:
        return {"ok": False, "error": "Bu aday son analizde yok."}
    ilk = (d.get("karar") or {}).get("secim")
    log({"olay": "onay", "secim": secim, "degisti": secim != ilk})
    d["onay"] = {"secim": secim, "degisti": secim != ilk}
    _yaz(d)
    return {"ok": True, "url": a["url"], "title": a["title"], "iddia_anahtar": (a.get("hazir") or {}).get("iddia_anahtar", "")}


def reddet():
    log({"olay": "red"})
    return {"ok": True}


# ----------------------------------------------------------------------------- guven olcutu
def log(kayit):
    kayit = dict(kayit)
    kayit.setdefault("zaman", datetime.datetime.now().isoformat(timespec="seconds"))
    try:
        os.makedirs(ENGINE, exist_ok=True)
        with open(GECMIS_YOL, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _gecmis(gun=GUVEN_GUN, now=None):
    now = now or datetime.datetime.now()
    esik = now - datetime.timedelta(days=gun)
    out = []
    try:
        with open(GECMIS_YOL, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                    if datetime.datetime.fromisoformat(r["zaman"]) >= esik:
                        out.append(r)
                except Exception:
                    continue
    except Exception:
        pass
    return out


def retention_kaydet(deger):
    try:
        v = float(str(deger).replace(",", "."))
    except Exception:
        return {"ok": False, "error": "Sayi gir (ornek 16,2)."}
    if not 0 <= v <= 100:
        return {"ok": False, "error": "0-100 arasi yuzde gir."}
    os.makedirs(ENGINE, exist_ok=True)
    with open(GIRIS_YOL, "w", encoding="utf-8") as f:
        json.dump({"retention": v, "zaman": datetime.datetime.now().isoformat(timespec="seconds")}, f)
    return {"ok": True, "retention": v}


def guven_durumu(now=None):
    """7 gun, uc sart: (1) koruma ihlali 0  (2) onerilerin >=%70'i degismeden onaylandi  (3) izlemeye devam >= taban (elle girilir).
    GUNDE EN FAZLA BIR oneri sayilir: ayni gun birkac kez 'Analizi baslat' basmak oneri sayisini sisirmez.
    Bir gunun onayi = o gunun SON onayi (degisti isareti ona gore)."""
    g = _gecmis(GUVEN_GUN, now)
    gun = lambda r: str(r.get("zaman", ""))[:10]
    oneri_gunleri = {gun(r) for r in g if r.get("olay") == "oneri"}
    son_onay = {}
    for r in sorted((r for r in g if r.get("olay") == "onay"), key=lambda r: r.get("zaman", "")):
        son_onay[gun(r)] = r
    degismeden_gunler = {d for d, r in son_onay.items() if not r.get("degisti") and d in oneri_gunleri}
    ihlal = [r for r in g if r.get("olay") == "ihlal"]
    oneri_n, ok_n = len(oneri_gunleri), len(degismeden_gunler)
    oran = (ok_n / oneri_n) if oneri_n else None
    try:
        with open(GIRIS_YOL, encoding="utf-8") as f:
            ret = json.load(f).get("retention")
    except Exception:
        ret = None
    s1 = len(ihlal) == 0
    s2 = oran is not None and oran >= ONAY_ESIGI and oneri_n >= GUVEN_GUN
    s3 = ret is not None and ret >= RETENTION_TABAN
    return {"gun": GUVEN_GUN, "oneri": oneri_n, "degismeden_onay": ok_n, "onay_orani": oran,
            "ihlal": len(ihlal), "retention": ret, "taban": RETENTION_TABAN,
            "sartlar": {"ihlal_yok": s1, "onay_orani": s2, "retention": s3},
            "otomatige_hazir": bool(s1 and s2 and s3)}
