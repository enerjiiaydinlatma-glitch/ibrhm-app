"""Kanaldaki mevcut videolarin DIL metadatasini Ingilizce'ye ceker (defaultLanguage / defaultAudioLanguage = en).

Kullanim:
  python dil_duzelt.py              # KURU CALISMA: neyin degisecegini listeler, HICBIR SEY yazmaz
  python dil_duzelt.py --uygula     # gercekten yazar (video basina 50 kota birimi; baslik/aciklama/etiket korunur)
  python dil_duzelt.py --uygula --en-fazla 10

Turkce altyazi parcalarina DOKUNMAZ (silmek icin Studio > Altyazilar; o ayri bir karar).
"""
import sys

import yukleme_meta as ym


def _servis():
    from googleapiclient.discovery import build
    from youtube_auth import get_credentials
    return build("youtube", "v3", credentials=get_credentials())


def kanal_videolari(yt, en_fazla=200):
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while len(ids) < en_fazla:
        r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        tok = r.get("nextPageToken")
        if not tok:
            break
    vids = []
    for i in range(0, len(ids[:en_fazla]), 50):
        vids += yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute().get("items", [])
    return vids


def main(argv):
    uygula = "--uygula" in argv
    limit = int(argv[argv.index("--en-fazla") + 1]) if "--en-fazla" in argv else 1000
    yt = _servis()
    vids = kanal_videolari(yt)
    plan = ym.dil_plani(vids)
    print(f"{len(vids)} video tarandi; dil alani eksik/farkli olan: {len(plan)}")
    for p in plan[:limit]:
        print(f"  {p['id']}  eski={p['eski']}  {p['baslik'][:60].encode('ascii', 'replace').decode('ascii')}")
    if not uygula:
        print("\nKURU CALISMA: hicbir sey yazilmadi. Yazmak icin:  python dil_duzelt.py --uygula")
        return 0
    by_id = {v["id"]: v for v in vids}
    n = 0
    for p in plan[:limit]:
        yt.videos().update(part="snippet", body=ym.guncelleme_govdesi(by_id[p["id"]])).execute()
        n += 1
    print(f"\n{n} videonun dil alani '{ym.DIL}' olarak guncellendi (~{n * 50} kota birimi).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
