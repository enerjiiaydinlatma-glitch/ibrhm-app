"""KONSEY ZAMANLA - ZATEN yuklenmis OZEL bir videoyu belirli bir saatte otomatik herkese acik olacak sekilde zamanlar. Baska hicbir seyi degistirmez.

Kullanim:  python konsey_zamanla.py VIDEO_ID --saat "2026-10-15 02:30"     (saat: TURKIYE saati)
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


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ozel bir videoyu zamanla")
    ap.add_argument("video_id")
    ap.add_argument("--saat", required=True, help="TURKIYE saati 'YYYY-MM-DD HH:MM'")
    a = ap.parse_args(argv)
    from googleapiclient.discovery import build
    from youtube_auth import get_credentials
    yt = build("youtube", "v3", credentials=get_credentials())
    items = yt.videos().list(part="snippet,status", id=a.video_id).execute().get("items", [])

    def onay(ozet):
        print(ozet)
        return sys.stdin.isatty() and input("Onayliyor musun? (evet/hayir) > ").strip().lower() in ("evet", "e", "yes", "y")
    ok, msgs = zamanla(items[0] if items else None, a.saat, lambda b: yt.videos().update(part="status", body=b).execute(), onay)
    for m in msgs:
        print(m)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
