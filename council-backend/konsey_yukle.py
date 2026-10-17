"""KONSEY OZEL YUKLEME - uretilmis bir Konsey Short'unu YouTube'a OZEL (private) yukler. HERKESE ACIK YAYINLAMAZ.

Kullanim:
  python konsey_yukle.py                 # en son uretilen Konsey Short'u (bilgiyi gosterir, ONAY ister)
  python konsey_yukle.py --meta output\\shorts\\topic\\xxx.json

Guvenlik (degismez):
- Varsayilan 'private'. Public/unlisted secenegi YOK. --zamanla 'YYYY-MM-DD HH:MM' (Turkiye saati) verilirse video private yuklenir ve
  o saatte YouTube tarafindan kendiliginden herkese acik olur: saati senin vermen ve ozeti onaylaman yayin onayidir; saat >=10 dk ileride, <=30 gun icinde olmali.
- Gunluk video siniri (daily_limit.MAX_DAILY) once kontrol edilir; --force YOK. Sayac mevcut sistemle ayni dosyayi kullanir
  (_engine/<tarih>/.uploaded_today.json).
- Yalnizca 'sabit_yorum' alani olan (make_topic_short --konsey ciktisi) meta dosyalarini yukler.
- Yuklemeden once baslik/aciklama/sayac gosterilir ve onay (evet) istenir.
- Dil: upload_youtube.upload_video defaultLanguage/defaultAudioLanguage = 'en' yazar (yukleme_meta).
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

import daily_limit
import konsey_format

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
TOPIC_DIR = os.path.join(HERE, "output", "shorts", "topic")
KAYIT_YOL = os.path.join(ENGINE, "konsey_kayit.jsonl")
ATLA = {"konsey_son_senaryo.json"}


TR_FARK = datetime.timedelta(hours=3)        # Turkiye sabit UTC+3
MIN_ILERI = datetime.timedelta(minutes=10)
MAX_ILERI = datetime.timedelta(days=30)


def zamanla_utc(metin, simdi_utc=None):
    """'YYYY-MM-DD HH:MM' (TURKIYE saati) -> 'YYYY-MM-DDTHH:MM:00Z'. Gecmis/cok yakin (<10 dk)/cok uzak (>30 gun) saat reddedilir (ValueError)."""
    simdi = simdi_utc or datetime.datetime.utcnow()
    try:
        tr = datetime.datetime.strptime((metin or "").strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("Saat bicimi 'YYYY-MM-DD HH:MM' (Turkiye saati) olmali, ornek: 2026-10-15 02:30")
    utc = tr - TR_FARK
    if utc < simdi + MIN_ILERI:
        raise ValueError("Zaman gecmiste ya da 10 dakikadan yakin; ileri bir saat ver.")
    if utc > simdi + MAX_ILERI:
        raise ValueError("Zaman 30 gunden uzak; daha yakin bir saat ver.")
    return utc.strftime("%Y-%m-%dT%H:%M:00Z")


def gunluk_dosya(bugun=None, engine=ENGINE):
    """aura_engine ile ayni sayac dosyasi: _engine/<YYYY-MM-DD>/.uploaded_today.json"""
    gun = (bugun or datetime.date.today()).isoformat()
    return os.path.join(engine, gun, ".uploaded_today.json")


def son_meta(klasor=TOPIC_DIR):
    """Klasordeki en yeni Konsey meta dosyasi (senaryo kaydi haric); yoksa None."""
    adaylar = [p for p in glob.glob(os.path.join(klasor, "*.json")) if os.path.basename(p) not in ATLA]
    return max(adaylar, key=os.path.getmtime) if adaylar else None


def ilk_cumle(script):
    return re.split(r"(?<=[.?!])\s", (script or "").strip())[0] if script else ""


def kontrol(meta, bugun=None, engine=ENGINE):
    """-> [mesaj]. Bos liste = yuklenebilir."""
    s = []
    if not meta.get("sabit_yorum"):
        s.append("Bu bir Konsey ciktisi degil (sabit_yorum yok); yalniz --konsey ile uretilenler yuklenir.")
    f = meta.get("file", "")
    if not f or not os.path.exists(f):
        s.append(f"Video dosyasi bulunamadi: {f or '(yok)'}")
    if not (meta.get("title") or "").strip():
        s.append("Baslik bos.")
    if len(meta.get("title", "")) > 100:
        s.append(f"Baslik {len(meta['title'])} karakter (YouTube siniri 100).")
    if not (meta.get("description") or "").strip():
        s.append("Aciklama bos.")
    ok, info = daily_limit.can_upload(gunluk_dosya(bugun, engine))
    if not ok:
        s.append(f"Gunluk sinira ulasildi ({info['count']}/{daily_limit.MAX_DAILY}); yeni yukleme YAPILMAZ.")
    return s


def yukleme_gunleri(yol=KAYIT_YOL):
    """konsey_kayit.jsonl'deki yukleme gunleri: {'YYYYMMDD', ...} (panel saglik kontrolleri icin)."""
    out = set()
    try:
        with open(yol, encoding="utf-8") as f:
            for ln in f:
                try:
                    ts = str(json.loads(ln).get("ts", ""))
                except Exception:
                    continue
                if len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
                    out.add(ts[:10].replace("-", ""))
    except OSError:
        pass
    return out


def kayit_yaz(meta, video_id, yol=KAYIT_YOL, simdi=None, yayin_utc=None):
    """Analiz icin etiket satiri (haftalik raporun sonraki surumu bunu kullanir)."""
    import haftalik_rapor
    import konsey_konular
    import rakam_bankasi
    hook = ilk_cumle(meta.get("script", ""))
    konu = meta.get("konu", "")
    kid = rakam_bankasi.konu_id(konu)
    kk = konsey_konular.konu_bul(kid) if kid is not None else None
    metin = f"{meta.get('script', '')} {meta.get('title', '')}"
    satir = {"video_id": video_id, "ts": (simdi or datetime.datetime.now()).isoformat(timespec="seconds"),
             "format": "konsey", "konu": konu, "baslik": meta.get("title", ""), "kanca": hook,
             "kanca_tipi": haftalik_rapor.kanca_tipi(hook), "cift": "alpha-beta", "gizlilik": "scheduled" if yayin_utc else "private", "yayin_utc": yayin_utc or "",
             # analiz icin (17 Ekim 2026): hangi sutun/konu, basliktaki rakam, kaynakli olgu kullanildi mi
             "konu_id": kid, "kategori": (kk or {}).get("kategori", ""),
             "baslikta_rakam": bool(re.search(r"\d", meta.get("title", ""))), "kaynakli_rakam": bool(rakam_bankasi.kaynak_satiri(konu, metin))}
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "a", encoding="utf-8") as f:
        f.write(json.dumps(satir, ensure_ascii=False) + "\n")
    return satir


def yukle(meta, upload, onay, bugun=None, engine=ENGINE, kayit_yolu=KAYIT_YOL, yayin_utc=None):
    """upload(file, title, description, tags, publish_at)->video_id (private; publish_at verilirse o ana kadar private). onay(metin)->bool.
    -> (video_id|None, mesajlar)"""
    sorun = kontrol(meta, bugun, engine)
    if sorun:
        return None, sorun
    gf = gunluk_dosya(bugun, engine)
    _ok, info = daily_limit.can_upload(gf)
    baslik = (f"\nYUKLENECEK ve ZAMANLANACAK: {yayin_utc} (UTC) tarihinde HERKESE ACIK olacak (o ana kadar ozel):"
              if yayin_utc else "\nYUKLENECEK (OZEL / private, herkese acik DEGIL):")
    ozet = (f"{baslik}\n  Baslik   : {meta['title']}\n  Dosya    : {meta['file']}\n"
            f"  Sure     : ~{meta.get('seconds', '?')} sn\n  Aciklama : {meta['description'].splitlines()[0]}\n"
            f"  Bugun    : {info['count']}/{daily_limit.MAX_DAILY} video yuklendi\n")
    if not onay(ozet):
        return None, ["Onay verilmedi, yuklenmedi."]
    etiket = konsey_format.etiketler(meta["title"].replace("#Shorts", ""))   # eski AI-haber etiketleri tasinmaz
    vid = upload(meta["file"], meta["title"], meta["description"], etiket, yayin_utc)
    os.makedirs(os.path.dirname(gf), exist_ok=True)
    daily_limit.record_upload(gf, vid)
    kayit_yaz(meta, vid, kayit_yolu, yayin_utc=yayin_utc)
    return vid, []


def _onay(metin):
    print(metin)
    if not sys.stdin.isatty():
        print("Etkilesimli terminal yok; onay alinamadi.")
        return False
    return input("Ozel olarak yuklensin mi? (evet/hayir) > ").strip().lower() in ("evet", "e", "yes", "y")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Konsey Short'unu OZEL yukle (yayinlamaz)")
    ap.add_argument("--meta", default=None, help="meta .json (varsayilan: en yeni Konsey ciktisi)")
    ap.add_argument("--zamanla", metavar="'YYYY-MM-DD HH:MM'", default=None,
                    help="TURKIYE saatiyle yayin zamani: video ozel yuklenir, o saatte kendiliginden herkese acik olur (saati veren onay verir)")
    a = ap.parse_args(argv)
    yayin = None
    if a.zamanla:
        try:
            yayin = zamanla_utc(a.zamanla)
        except ValueError as e:
            print(e)
            return 2
    yol = a.meta or son_meta()
    if not yol:
        print(f"Meta dosyasi bulunamadi: {TOPIC_DIR}")
        return 2
    with open(yol, encoding="utf-8") as f:
        meta = json.load(f)

    def upload(file, title, desc, tags, publish_at=None):
        from upload_youtube import upload_video
        return upload_video(file, title, desc, tags=tags, privacy_status="private", publish_at=publish_at)
    vid, mesajlar = yukle(meta, upload, _onay, yayin_utc=yayin)
    if not vid:
        for m in mesajlar:
            print(m)
        return 2
    if yayin:
        print(f"\nYUKLENDI ve ZAMANLANDI: https://youtu.be/{vid}  ({a.zamanla} TR saatinde kendiliginden herkese acik olacak)")
        print("\nSIRADAKI (yalniz bu, Studio'da): video yayinlaninca su yorumu yaz ve SABITLE (API yorum sabitlemeyi desteklemez):")
    else:
        print(f"\nYUKLENDI (OZEL): https://youtu.be/{vid}")
        print("\nSIRADAKI: yayin icin bir sonraki seferde --zamanla 'YYYY-MM-DD HH:MM' kullan (Studio'ya gerek kalmaz).")
        print("Yayinlandiktan sonra su yorumu yaz ve SABITLE (API yorum sabitlemeyi desteklemez):")
    print(f"     {meta['sabit_yorum']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
