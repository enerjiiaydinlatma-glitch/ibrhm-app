"""KONSEY KONTROL - yuklenen Konsey videolarinin durumunu ve sayilarini tek komutla gosterir. YouTube'a HICBIR sey yazmaz.

Kullanim:  python konsey_kontrol.py          (_engine/konsey_kayit.jsonl'deki videolar)
           python konsey_kontrol.py --id XXXXXXXXXXX --id YYYYYYYYYYY   (ek video)
Gosterir: baslik, gizlilik (private / zamanlandi / HERKESE ACIK), yayin zamani, izlenme, begeni, yorum.
Ulke dagilimi icin Studio > Analytics > Ulke (burada yok).
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KAYIT_YOL = os.path.join(HERE, "_engine", "konsey_kayit.jsonl")


def kayitli_idler(yol=KAYIT_YOL):
    out = []
    try:
        with open(yol, encoding="utf-8") as f:
            for ln in f:
                try:
                    vid = json.loads(ln).get("video_id")
                except Exception:
                    continue
                if vid and vid not in out:
                    out.append(vid)
    except OSError:
        pass
    return out


def durum(item):
    """videos.list ogesi -> okunur gizlilik durumu."""
    st = item.get("status", {})
    if st.get("publishAt"):
        return f"ZAMANLANDI -> {st['publishAt']} (UTC)"
    return {"private": "ozel (private)", "public": "HERKESE ACIK", "unlisted": "liste disi"}.get(st.get("privacyStatus"), st.get("privacyStatus", "?"))


def yas_saat(item, simdi_utc=None):
    """Videonun yayinda gecirdigi saat (publishedAt'ten); zamanli/ozel videoda None."""
    st = item.get("status", {})
    if st.get("publishAt") or st.get("privacyStatus") != "public":
        return None
    try:
        yayin = datetime.datetime.strptime(item["snippet"]["publishedAt"][:19], "%Y-%m-%dT%H:%M:%S")
    except (KeyError, ValueError):
        return None
    simdi = simdi_utc or datetime.datetime.utcnow()
    return max((simdi - yayin).total_seconds() / 3600, 0.0)


def satirlar(items, istenen, simdi_utc=None):
    bulunan = {it["id"]: it for it in items}
    out = []
    for vid in istenen:
        it = bulunan.get(vid)
        if not it:
            out.append(f"{vid}: BULUNAMADI (silinmis ya da erisim yok)")
            continue
        s = it.get("statistics", {})
        yas = yas_saat(it, simdi_utc)
        hiz = ""
        if yas is not None:
            izl = int(s.get("viewCount", 0))
            hiz = f" | Yas: {yas:.0f} sa | Saatlik: {izl / yas:.2f}" if yas >= 1 else f" | Yas: {yas:.1f} sa (cok yeni)"
        out.append(f"{it['snippet']['title']}\n  https://youtu.be/{vid}\n  Durum: {durum(it)} | yayin: {it['snippet'].get('publishedAt', '?')}\n"
                   f"  Izlenme: {s.get('viewCount', '0')} | Begeni: {s.get('likeCount', '0')} | Yorum: {s.get('commentCount', '0')}{hiz}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Konsey videolarinin durumu (okuma)")
    ap.add_argument("--id", action="append", default=[], help="ek video id")
    a = ap.parse_args(argv)
    ids = kayitli_idler() + [i for i in a.id if i not in kayitli_idler()]
    if not ids:
        print("Kayitli video yok (_engine/konsey_kayit.jsonl) ve --id verilmedi.")
        return 2
    from googleapiclient.discovery import build
    from youtube_auth import get_credentials
    yt = build("youtube", "v3", credentials=get_credentials())
    items = yt.videos().list(part="snippet,status,statistics", id=",".join(ids)).execute().get("items", [])
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n\n".join(satirlar(items, ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
