"""KONSEY ZAMANLA - ZATEN yuklenmis OZEL bir videoyu belirli bir saatte otomatik herkese acik olacak sekilde zamanlar. Baska hicbir seyi degistirmez.

Kullanim:  python konsey_zamanla.py VIDEO_ID --saat "2026-10-15 02:30"     (saat: TURKIYE saati)
           python konsey_zamanla.py VIDEO_ID --iptal                        (zamanlamayi KALDIRIR; video OZEL kalir, yayinlanmaz)
Guvenlik: yalniz 'private' videoyu zamanlar (zaten herkese acik/liste disi video reddedilir); saat >=10 dk ileri, <=30 gun icinde;
onay ister (evet). Sadece 'status' alani guncellenir (baslik/aciklama/etiket dokunulmaz).
"""
import argparse
import sys

import konsey_yukle


def kontrol(item):
    """videos.list ogesi -> [mesaj]. Bos = zamanlanabilir."""
    if not item:
        return ["Video bulunamadi (id yanlis ya da erisim yok)."]
    gz = item.get("status", {}).get("privacyStatus")
    if gz != "private":
        return [f"Video 'private' degil ({gz}); yalniz ozel videolar zamanlanir. Dokunulmadi."]
    return []


def govde(video_id, yayin_utc):
    return {"id": video_id, "status": {"privacyStatus": "private", "publishAt": yayin_utc, "selfDeclaredMadeForKids": False}}


def zamanla(item, saat_tr, update, onay, simdi_utc=None):
    """update(body)->None. -> (basarili, mesajlar)"""
    sorun = kontrol(item)
    if sorun:
        return False, sorun
    try:
        yayin = konsey_yukle.zamanla_utc(saat_tr, simdi_utc)
    except ValueError as e:
        return False, [str(e)]
    eski = item.get("status", {}).get("publishAt")
    ozet = (f"\nZAMANLANACAK: {item['snippet']['title']}\n  https://youtu.be/{item['id']}\n  Yayin: {saat_tr} TR ({yayin} UTC) - o anda HERKESE ACIK olur"
            + (f"\n  (su an zamanli: {eski}, degisecek)" if eski else "") + "\n")
    if not onay(ozet):
        return False, ["Onay verilmedi, degistirilmedi."]
    update(govde(item["id"], yayin))
    return True, [f"Zamanlandi: {saat_tr} TR ({yayin} UTC)."]


def iptal_kontrol(item):
    if not item:
        return ["Video bulunamadi (id yanlis ya da erisim yok)."]
    st = item.get("status", {})
    if st.get("privacyStatus") != "private":
        return [f"Video 'private' degil ({st.get('privacyStatus')}); yalniz zamanlanmis OZEL video iptal edilir. Dokunulmadi."]
    if not st.get("publishAt"):
        return ["Video zaten zamanlanmamis (publishAt yok); yapilacak bir sey yok."]
    return []


def iptal(item, update, onay):
    """Zamanlamayi kaldirir: privacyStatus 'private' kalir, publishAt YOLLANMAZ. update(body)->None. -> (basarili, mesajlar)"""
    sorun = iptal_kontrol(item)
    if sorun:
        return False, sorun
    ozet = (f"\nZAMANLAMA IPTAL EDILECEK: {item['snippet']['title']}\n  https://youtu.be/{item['id']}\n"
            f"  Su an zamanli: {item['status']['publishAt']} -> yayinlanmayacak, OZEL kalacak (video silinmez)\n")
    if not onay(ozet):
        return False, ["Onay verilmedi, degistirilmedi."]
    # publishAt'i YOLLAMAMAK zamanlamayi kaldirmadi (gercek API ile dogrulandi, 27 Eki 2026): acikca null gonderilir; sonuc ayrica DOGRULANIR (main).
    update({"id": item["id"], "status": {"privacyStatus": "private", "publishAt": None, "selfDeclaredMadeForKids": False}})
    return True, ["Zamanlama iptal istegi gonderildi."]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ozel bir videoyu zamanla")
    ap.add_argument("video_id")
    ap.add_argument("--saat", help="TURKIYE saati 'YYYY-MM-DD HH:MM'")
    ap.add_argument("--iptal", action="store_true", help="zamanlamayi kaldir (video ozel kalir)")
    a = ap.parse_args(argv)
    if not a.iptal and not a.saat:
        ap.error("--saat ya da --iptal gerekli")
    from googleapiclient.discovery import build
    from youtube_auth import get_credentials
    yt = build("youtube", "v3", credentials=get_credentials())
    items = yt.videos().list(part="snippet,status", id=a.video_id).execute().get("items", [])

    def onay(ozet):
        print(ozet)
        return sys.stdin.isatty() and input("Onayliyor musun? (evet/hayir) > ").strip().lower() in ("evet", "e", "yes", "y")
    guncelle = lambda b: yt.videos().update(part="status", body=b).execute()  # noqa: E731
    if a.iptal:
        ok, msgs = iptal(items[0] if items else None, guncelle, onay)
        if ok:
            son = yt.videos().list(part="status", id=a.video_id).execute().get("items", [{}])[0].get("status", {})
            kalan = son.get("publishAt")
            msgs.append("Dogrulama: publishAt=" + (kalan or "yok (temiz)") + f", gizlilik={son.get('privacyStatus')}")
            if kalan:
                msgs.append("UYARI: ZAMANLAMA KALKMADI, video hala " + kalan + " tarihinde yayinlanacak! Studio -> Icerik -> video -> Gorunurluk -> Ozel -> Kaydet (elle) "
                            "ya da videoyu silin.")
                ok = False
    else:
        ok, msgs = zamanla(items[0] if items else None, a.saat, guncelle, onay)
    for m in msgs:
        print(m)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
