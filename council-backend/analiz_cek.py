"""ANALIZ CEK - YouTube Analytics API'den kanal verisini ceker, Turkce ozet yazar, CSV birakir. YALNIZ OKUR; hicbir seyi degistirmez/yayinlamaz.

Kullanim:
  python analiz_cek.py --yetkilendir     # TEK SEFERLIK: tarayicidan 'yalniz okuma' izni (yt-analytics.readonly + youtube.readonly)
  python analiz_cek.py                   # son 60 gun
  python analiz_cek.py --gun 28
  python analiz_cek.py --bas 2026-08-27 --bit 2026-09-23     # ONCEKI DONEM (neden 10 kat daha cok izleniyordu?)

Cikti: konsolda ozet + _engine/analiz_<bas>_<bit>_{gunluk,video,kaynak}.csv.
Notlar:
- Yetki dosyasi: youtube_analytics_token.json (GIZLI, repoya girmez). client_secret.json gerekir (youtube_auth.py ile ayni dosya).
- 'engagedViews' (Shorts'ta gercekten izlenen) API'de varsa eklenir; yoksa sessizce atlanir. 'Izlendi/kaydirildi' yuzdesi API'de herkese acik DEGILDIR: Studio'dan elle bakilir.
- Bu dosya henuz gercek API ile denenmedi (testler yalniz saf fonksiyonlari kapsar); ilk calistirmada hata verirse mesaji yapistirin.
"""
import argparse
import csv
import datetime
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
KAYIT_YOL = os.path.join(ENGINE, "konsey_kayit.jsonl")
CLIENT_SECRET = os.path.join(HERE, "client_secret.json")
TOKEN = os.path.join(HERE, "youtube_analytics_token.json")
SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"]

GUNLUK_METRIK = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,comments,shares"
VIDEO_METRIK = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,comments,shares"


# --------------------------------------------------------------------------- saf fonksiyonlar (test edilebilir)
def satirlar(yanit):
    """Analytics API yaniti -> [dict]. columnHeaders adlariyla satirlari eslestirir."""
    basliklar = [h["name"] for h in (yanit or {}).get("columnHeaders", [])]
    return [dict(zip(basliklar, r)) for r in (yanit or {}).get("rows", []) or []]


def medyan(degerler):
    d = [x for x in degerler if x is not None]
    return round(statistics.median(d), 1) if d else None


def kayit_oku(yol=KAYIT_YOL):
    """konsey_kayit.jsonl -> {video_id: kayit}"""
    out = {}
    try:
        with open(yol, encoding="utf-8") as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if d.get("video_id"):
                    out[d["video_id"]] = d
    except OSError:
        pass
    return out


def kategori_gruplari(video_satirlari, kayit):
    """[{'video': id, 'views': n, ...}] + kayit -> kategori basina {n, medyan_goruntuleme, ort_izleme_yuzde_medyan}. Kayitta olmayan 'diger'."""
    g = {}
    for r in video_satirlari:
        k = (kayit.get(r.get("video")) or {}).get("kategori") or ("diger" if r.get("video") not in kayit else "kategorisiz")
        g.setdefault(k, []).append(r)
    return {k: {"n": len(v), "medyan_goruntuleme": medyan([x.get("views") for x in v]),
                "medyan_izleme_yuzde": medyan([x.get("averageViewPercentage") for x in v])} for k, v in g.items()}


def ozet_metni(gunluk, videolar, kaynaklar, basliklar, kayit):
    """Turkce kisa ozet. gunluk/videolar/kaynaklar: satirlar() ciktisi; basliklar: {id: baslik}."""
    s = []
    toplam = sum(r.get("views", 0) or 0 for r in gunluk)
    dakika = sum(r.get("estimatedMinutesWatched", 0) or 0 for r in gunluk)
    abone = sum(r.get("subscribersGained", 0) or 0 for r in gunluk)
    s.append(f"TOPLAM: {toplam} goruntuleme, {round(dakika / 60, 1)} saat izlenme, +{abone} abone ({len(gunluk)} gun)")
    if gunluk:
        enust = max(gunluk, key=lambda r: r.get("views", 0) or 0)
        s.append(f"  en yogun gun: {enust.get('day')} ({enust.get('views')} goruntuleme); gunluk medyan: {medyan([r.get('views') for r in gunluk])}")
    if kaynaklar:
        top = sum(r.get("views", 0) or 0 for r in kaynaklar) or 1
        s.append("KAYNAKLAR: " + ", ".join(f"{r.get('insightTrafficSourceType')} %{round(100 * (r.get('views', 0) or 0) / top, 1)}"
                                        for r in sorted(kaynaklar, key=lambda x: -(x.get("views", 0) or 0))[:5]))
    s.append(f"VIDEOLAR ({len(videolar)}); medyan goruntuleme: {medyan([r.get('views') for r in videolar])}, medyan ort. izleme %: {medyan([r.get('averageViewPercentage') for r in videolar])}")
    for r in sorted(videolar, key=lambda x: -(x.get("views", 0) or 0))[:10]:
        vid = r.get("video")
        s.append(f"  {r.get('views'):>5} gor | ort.izleme %{round(r.get('averageViewPercentage') or 0, 1):>5} | +{r.get('subscribersGained', 0)} abone | "
                 f"{r.get('likes', 0)} begeni | {r.get('comments', 0)} yorum | {basliklar.get(vid) or (kayit.get(vid) or {}).get('baslik') or vid}")
    gr = kategori_gruplari(videolar, kayit)
    if len(gr) > 1 or "diger" not in gr:
        s.append("SUTUNLAR (yalniz konsey_kayit.jsonl'de kategorisi olan videolar): " + "; ".join(
            f"{k}: n={v['n']}, medyan {v['medyan_goruntuleme']} gor, izleme %{v['medyan_izleme_yuzde']}" for k, v in sorted(gr.items())))
    return "\n".join(s)


def csv_yaz(yol, satir_listesi):
    if not satir_listesi:
        return False
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    alanlar = sorted({k for r in satir_listesi for k in r})
    with open(yol, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alanlar)
        w.writeheader()
        w.writerows(satir_listesi)
    return True


def tarih_araligi(gun=60, bas=None, bit=None, bugun=None):
    bugun = bugun or datetime.date.today()
    if bas and bit:
        return bas, bit
    return (bugun - datetime.timedelta(days=gun)).isoformat(), (bugun - datetime.timedelta(days=1)).isoformat()


# --------------------------------------------------------------------------- API (yalniz okuma)
def yetkilendir():
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not os.path.exists(CLIENT_SECRET):
        raise SystemExit("client_secret.json yok (youtube_auth.py ile ayni dosya). council-backend klasorune koyun.")
    creds = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES).run_local_server(port=0)
    with open(TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"Yetki kaydedildi: {TOKEN} (YALNIZ OKUMA izni; gizli dosya, repoya EKLEME)")


def _servisler():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    if not os.path.exists(TOKEN):
        raise SystemExit("Yetki yok: once 'python analiz_cek.py --yetkilendir' calistirin.")
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise SystemExit("Yetki gecersiz: 'python analiz_cek.py --yetkilendir' ile yenileyin.")
    return build("youtubeAnalytics", "v2", credentials=creds), build("youtube", "v3", credentials=creds)


def _sorgu(ya, bas, bit, metrik, boyut=None, sirala=None, maks=None):
    kw = dict(ids="channel==MINE", startDate=bas, endDate=bit, metrics=metrik)
    if boyut:
        kw["dimensions"] = boyut
    if sirala:
        kw["sort"] = sirala
    if maks:
        kw["maxResults"] = maks
    return satirlar(ya.reports().query(**kw).execute())


def basliklari_al(yt, idler):
    out = {}
    idler = list(idler)
    for i in range(0, len(idler), 50):
        yanit = yt.videos().list(part="snippet", id=",".join(idler[i:i + 50])).execute()
        for it in yanit.get("items", []):
            out[it["id"]] = it["snippet"]["title"]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="YouTube Analytics'ten kanal verisini cek (yalniz okur)")
    ap.add_argument("--yetkilendir", action="store_true")
    ap.add_argument("--gun", type=int, default=60)
    ap.add_argument("--bas")
    ap.add_argument("--bit")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.yetkilendir:
        yetkilendir()
        return 0
    bas, bit = tarih_araligi(a.gun, a.bas, a.bit)
    ya, yt = _servisler()
    gunluk = _sorgu(ya, bas, bit, GUNLUK_METRIK, "day", "day")
    try:
        videolar = _sorgu(ya, bas, bit, VIDEO_METRIK + ",engagedViews", "video", "-views", 50)
    except Exception:
        videolar = _sorgu(ya, bas, bit, VIDEO_METRIK, "video", "-views", 50)
    kaynaklar = _sorgu(ya, bas, bit, "views", "insightTrafficSourceType", "-views")
    basliklar = basliklari_al(yt, [r["video"] for r in videolar if r.get("video")])
    kayit = kayit_oku()
    print(f"\nDONEM: {bas} -> {bit}\n")
    print(ozet_metni(gunluk, videolar, kaynaklar, basliklar, kayit))
    etiket = f"{bas}_{bit}"
    for ad, veri in (("gunluk", gunluk), ("video", [{**r, "baslik": basliklar.get(r.get("video"), "")} for r in videolar]), ("kaynak", kaynaklar)):
        if csv_yaz(os.path.join(ENGINE, f"analiz_{etiket}_{ad}.csv"), veri):
            print(f"  [csv] _engine/analiz_{etiket}_{ad}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
