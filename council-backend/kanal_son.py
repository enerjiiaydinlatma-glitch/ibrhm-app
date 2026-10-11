"""KANAL KARNESI - son videolarin CANLI sayilari (YouTube Data API; Analytics gecikmesi yok). SALT OKUNUR.

Kullanim:  python kanal_son.py            (son 12 video)
           python kanal_son.py 20         (son 20 video)

Her video icin: yas (saat), izlenme, begeni, yorum, gizlilik, ve izlenmenin kanalin kendi MEDYANINA orani.
Dikkat: ornek cok kucuk (izlenmeler tek hanede) - oranlar gurultuye acik, KANIT degil YON gostergesidir.
Hicbir sey yazmaz/degistirmez; yukleme, yayin, kayit yok.
"""
import datetime
import statistics
import sys

OLGUN_SAAT = 72  # medyan hesabina yalniz bu yasi gecen herkese acik videolar girer


def _yas_saat(published, now):
    try:
        t = datetime.datetime.fromisoformat(published.replace("Z", "+00:00")).replace(tzinfo=None)
        return max((now - t).total_seconds() / 3600.0, 0.0)
    except Exception:
        return None


def karne(videolar, now=None):
    """videolar: analiz.kanal_videolari()['videolar'] -> satir listesi (yeniden eskiye)."""
    now = now or datetime.datetime.utcnow()
    sirali = sorted(videolar, key=lambda v: v.get("published", ""), reverse=True)
    olgun = [v["views"] for v in sirali
             if v.get("privacy", "public") == "public" and (_yas_saat(v.get("published", ""), now) or 0) >= OLGUN_SAAT]
    medyan = statistics.median(olgun) if olgun else None
    rows = []
    for v in sirali:
        yas = _yas_saat(v.get("published", ""), now)
        oran = None
        if medyan and yas is not None and yas >= OLGUN_SAAT and v.get("privacy", "public") == "public":
            oran = round(v["views"] / medyan, 2)
        rows.append({"id": v["id"], "gun": v.get("published", "")[:10], "yas_saat": None if yas is None else round(yas, 1),
                     "izlenme": v["views"], "begeni": v["likes"], "yorum": v["comments"],
                     "gizlilik": v.get("privacy", ""), "medyana_oran": oran, "baslik": v.get("title", "")})
    return {"medyan_izlenme": medyan, "olgun_video": len(olgun), "satirlar": rows}


def main(argv):
    n = 12
    if len(argv) > 1 and argv[1].isdigit():
        n = min(int(argv[1]), 50)
    import analiz
    r = analiz.kanal_videolari(max_sonuc=n)
    if not r.get("ok"):
        print("[HATA] YouTube verisi alinamadi:", r.get("hata"))
        return 1
    k = karne(r["videolar"])
    print(f"Kanal medyan izlenme (>= {OLGUN_SAAT} saat yasli herkese acik {k['olgun_video']} video): {k['medyan_izlenme']}")
    print("gun        yas_s  izlenme  begeni  yorum  gizlilik  medyana_oran  baslik")
    for s in k["satirlar"]:
        oran = "-" if s["medyana_oran"] is None else f"{s['medyana_oran']}x"
        yas = "?" if s["yas_saat"] is None else f"{s['yas_saat']:.0f}"
        baslik = s["baslik"][:52].encode("ascii", "replace").decode("ascii")
        print(f"{s['gun']}  {yas:>5}  {s['izlenme']:>7}  {s['begeni']:>6}  {s['yorum']:>5}  {s['gizlilik']:<8}  {oran:>12}  {baslik}")
    print("\nNot: ornek cok kucuk; oranlar yon gostergesidir, kanit degil.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
