"""KONSEY OZEL YUKLEME - uretilmis bir Konsey Short'unu YouTube'a OZEL (private) yukler. HERKESE ACIK YAYINLAMAZ.

Kullanim:
  python konsey_yukle.py                 # en son uretilen Konsey Short'u (bilgiyi gosterir, ONAY ister)
  python konsey_yukle.py --meta output\\shorts\\topic\\xxx.json

Guvenlik (degismez):
- Yalnizca 'private'. Public/unlisted/zamanlama secenegi YOK; yayin karari Studio'da insanda.
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


def kayit_yaz(meta, video_id, yol=KAYIT_YOL, simdi=None):
    """Analiz icin etiket satiri (haftalik raporun sonraki surumu bunu kullanir)."""
    import haftalik_rapor
    hook = ilk_cumle(meta.get("script", ""))
    satir = {"video_id": video_id, "ts": (simdi or datetime.datetime.now()).isoformat(timespec="seconds"),
             "format": "konsey", "baslik": meta.get("title", ""), "kanca": hook,
             "kanca_tipi": haftalik_rapor.kanca_tipi(hook), "cift": "alpha-beta", "gizlilik": "private"}
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "a", encoding="utf-8") as f:
        f.write(json.dumps(satir, ensure_ascii=False) + "\n")
    return satir


def yukle(meta, upload, onay, bugun=None, engine=ENGINE, kayit_yolu=KAYIT_YOL):
    """upload(file, title, description, tags)->video_id (private). onay(metin)->bool. -> (video_id|None, mesajlar)"""
    sorun = kontrol(meta, bugun, engine)
    if sorun:
        return None, sorun
    gf = gunluk_dosya(bugun, engine)
    _ok, info = daily_limit.can_upload(gf)
    ozet = (f"\nYUKLENECEK (OZEL / private, herkese acik DEGIL):\n  Baslik   : {meta['title']}\n  Dosya    : {meta['file']}\n"
            f"  Sure     : ~{meta.get('seconds', '?')} sn\n  Aciklama : {meta['description'].splitlines()[0]}\n"
            f"  Bugun    : {info['count']}/{daily_limit.MAX_DAILY} video yuklendi\n")
    if not onay(ozet):
        return None, ["Onay verilmedi, yuklenmedi."]
    etiket = konsey_format.etiketler(meta["title"].replace("#Shorts", ""))   # eski AI-haber etiketleri tasinmaz
    vid = upload(meta["file"], meta["title"], meta["description"], etiket)
    os.makedirs(os.path.dirname(gf), exist_ok=True)
    daily_limit.record_upload(gf, vid)
    kayit_yaz(meta, vid, kayit_yolu)
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
    a = ap.parse_args(argv)
    yol = a.meta or son_meta()
    if not yol:
        print(f"Meta dosyasi bulunamadi: {TOPIC_DIR}")
        return 2
    with open(yol, encoding="utf-8") as f:
        meta = json.load(f)

    def upload(file, title, desc, tags):
        from upload_youtube import upload_video
        return upload_video(file, title, desc, tags=tags, privacy_status="private")
    vid, mesajlar = yukle(meta, upload, _onay)
    if not vid:
        for m in mesajlar:
            print(m)
        return 2
    print(f"\nYUKLENDI (OZEL): https://youtu.be/{vid}")
    print("\nSIRADAKI (Studio, sen yaparsin):")
    print("  1) studio.youtube.com > Icerik > videoyu ac, izle.")
    print("  2) Gorunurluk: 'Zamanla' sec, ABD aksami (~02:00-04:00 TR) bir saat belirle. Yayin karari sende.")
    print("  3) Yayinlandiktan sonra su yorumu yaz ve SABITLE (API yorum sabitlemeyi desteklemez):")
    print(f"     {meta['sabit_yorum']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
