"""KANAL TEMIZLE - eski (Konsey oncesi) herkese acik videolari OZEL'e alir. SILMEZ; her adim geri alinabilir (--geri-al).

Neden (29-31 Eki 2026): eski AI-haber hattinin ~25 videosu 1-4 goruntuleme aliyor ve bazi basliklari degismez kurallarimiza aykiri
(niyet atfi / suc dili / gercek sirket). Kanal kimligini tutarli kilmak ve riski kaldirmak icin Ozel'e alinir. Kanal tahsisi (dagitim) cokmus durumda; silmeye gerek yok.

Kullanim:
  python kanal_temizle.py                         # ONIZLEME: aday listesi (hicbir sey degismez)
  python kanal_temizle.py --riskli-sadece         # yalniz claim_lint'e takilan basliklar
  python kanal_temizle.py --uygula                # listeyi gosterir, 'evet' ister, Ozel'e alir, kaydi _engine/kanal_temizle_<tarih>.json'a yazar
  python kanal_temizle.py --geri-al _engine/kanal_temizle_20261031_1200.json   # kayittaki videolari yeniden herkese acik yapar (evet ister)

Aday = herkese acik + yayin tarihi --kesim'den ONCE + konsey_kayit.jsonl'de OLMAYAN. Konsey videolari ve yeni videolar asla aday degildir.
Sadece 'status' guncellenir (mevcut ayarlar korunur; yalniz privacyStatus 'private' olur).
"""
import argparse
import datetime
import json
import os
import re
import sys

import claim_lint

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
KAYIT_YOL = os.path.join(ENGINE, "konsey_kayit.jsonl")
VARSAYILAN_KESIM = "2026-10-13"
YAZILABILIR = ("privacyStatus", "embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids")


def sure_sn(iso):
    """ISO 8601 sure ('PT1M37S') -> saniye."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    g, s, d, sn = (int(x or 0) for x in m.groups())
    return g * 86400 + s * 3600 + d * 60 + sn


# claim_lint parca/kelime tabanli ve cogu niyet/suc ima eden basligi YAKALAMIYOR ('stolen data', 'cartel collusion charges', 'designed to protect X',
# 'to block competitors' gecerli sayiliyor). Editoryal ek liste: niyet atfi / suc dili / gizlilik ima eden kaliplar (okuyarak belirlendi).
EK_RISK = re.compile(r"\b(stolen|steal\w*|theft|collusion|cartel|fraud\w*|illegal\w*|to block|designed to|quietly|neutrali[sz]e|excuse to|erasing)\b", re.I)


def riskli(baslik):
    """Basligin claim_lint engelleyici isabetleri + editoryal ek liste (EK_RISK) isabetleri."""
    r = {ad for ad, _h, _w in claim_lint.lint(baslik or "") if ad in claim_lint.BLOCKING}
    r |= {f"EK:{m.group(0).lower()}" for m in EK_RISK.finditer(baslik or "")}
    return sorted(r)


def adaylar(videolar, konsey_idleri, kesim=VARSAYILAN_KESIM, riskli_sadece=False):
    """videolar: videos.list ogeleri. -> [dict(id, baslik, yayin, sure, izlenme, riskler)] izlenme sirali."""
    out = []
    for v in videolar:
        st, sn = v.get("status", {}), v.get("snippet", {})
        yayin = (sn.get("publishedAt") or "")[:10]
        if v.get("id") in konsey_idleri or st.get("privacyStatus") != "public" or not yayin or yayin >= kesim:
            continue
        r = riskli(sn.get("title", ""))
        if riskli_sadece and not r:
            continue
        out.append({"id": v["id"], "baslik": sn.get("title", ""), "yayin": yayin, "sure": sure_sn(v.get("contentDetails", {}).get("duration")),
                    "izlenme": int(v.get("statistics", {}).get("viewCount", 0) or 0), "riskler": r,
                    "durum_eski": {k: st[k] for k in YAZILABILIR if k in st}})
    return sorted(out, key=lambda x: -x["izlenme"])


def govde(aday, gizlilik):
    """Mevcut yazilabilir ayarlari koruyup yalniz gizliligi degistirir (publishAt YOLLANMAZ)."""
    st = dict(aday["durum_eski"])
    st["privacyStatus"] = gizlilik
    return {"id": aday["id"], "status": st}


def rapor(adaylar_):
    s = [f"{len(adaylar_)} aday (herkese acik, eski hat, Konsey degil):"]
    for a in adaylar_:
        s.append(f"  {a['izlenme']:>5} gor | {a['sure']//60}:{a['sure']%60:02d} | {a['yayin']} | {a['id']} | {a['baslik'][:78]}"
                 + (f"  [RISKLI: {', '.join(a['riskler'])}]" if a["riskler"] else ""))
    return "\n".join(s)


def konsey_idleri(yol=KAYIT_YOL):
    out = set()
    try:
        with open(yol, encoding="utf-8") as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if d.get("video_id"):
                    out.add(d["video_id"])
    except OSError:
        pass
    return out


def uygula(adaylar_, update, onay, kayit_yolu):
    """update(body)->None. -> (yapilan, mesajlar). Onay yoksa HICBIR sey degismez."""
    if not adaylar_:
        return [], ["Aday yok."]
    if not onay(rapor(adaylar_) + "\n\nBunlar OZEL'e alinacak (silinmeyecek, geri alinabilir)."):
        return [], ["Onay verilmedi, hicbir sey degismedi."]
    yapilan = []
    for a in adaylar_:
        update(govde(a, "private"))
        yapilan.append({k: a[k] for k in ("id", "baslik", "izlenme", "durum_eski")})
    os.makedirs(os.path.dirname(kayit_yolu), exist_ok=True)
    with open(kayit_yolu, "w", encoding="utf-8") as f:
        json.dump({"zaman": datetime.datetime.now().isoformat(timespec="seconds"), "videolar": yapilan}, f, ensure_ascii=False, indent=2)
    return yapilan, [f"{len(yapilan)} video Ozel'e alindi. Kayit: {kayit_yolu}"]


def geri_al(kayit, update, onay):
    """Kayittaki videolari kayittaki ESKI ayarlariyla yeniden yayimlar (onay ister)."""
    vs = kayit.get("videolar", [])
    if not vs or not onay(f"{len(vs)} video yeniden HERKESE ACIK yapilacak (eski ayarlariyla). Devam?"):
        return 0, ["Geri alma yapilmadi."]
    for v in vs:
        st = dict(v.get("durum_eski", {}))
        st["privacyStatus"] = "public"
        update({"id": v["id"], "status": st})
    return len(vs), [f"{len(vs)} video yeniden herkese acik."]


def _servis():
    from googleapiclient.discovery import build
    from youtube_auth import get_credentials
    return build("youtube", "v3", credentials=get_credentials())


def tum_videolar(yt):
    kanal = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    liste = kanal["contentDetails"]["relatedPlaylists"]["uploads"]
    idler, sayfa = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=liste, maxResults=50, pageToken=sayfa).execute()
        idler += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        sayfa = r.get("nextPageToken")
        if not sayfa:
            break
    out = []
    for i in range(0, len(idler), 50):
        out += yt.videos().list(part="snippet,status,statistics,contentDetails", id=",".join(idler[i:i + 50])).execute().get("items", [])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eski videolari Ozel'e al (silmez, geri alinabilir)")
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--riskli-sadece", action="store_true")
    ap.add_argument("--kesim", default=VARSAYILAN_KESIM, help="bu tarihten ONCE yayinlananlar (YYYY-MM-DD)")
    ap.add_argument("--geri-al", metavar="KAYIT.json")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    yt = _servis()
    guncelle = lambda b: yt.videos().update(part="status", body=b).execute()  # noqa: E731

    def onay(metin):
        print(metin)
        return sys.stdin.isatty() and input("Onayliyor musun? (evet/hayir) > ").strip().lower() in ("evet", "e", "yes", "y")
    if a.geri_al:
        with open(a.geri_al, encoding="utf-8") as f:
            n, msg = geri_al(json.load(f), guncelle, onay)
        print("\n".join(msg))
        return 0 if n else 2
    adaylar_ = adaylar(tum_videolar(yt), konsey_idleri(), a.kesim, a.riskli_sadece)
    if not a.uygula:
        print(rapor(adaylar_))
        print("\n(Onizleme. Ozel'e almak icin: python kanal_temizle.py --uygula)")
        return 0
    kayit = os.path.join(ENGINE, f"kanal_temizle_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json")
    yapilan, msg = uygula(adaylar_, guncelle, onay, kayit)
    print("\n".join(msg))
    return 0 if yapilan else 2


if __name__ == "__main__":
    sys.exit(main())
