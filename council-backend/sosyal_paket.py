"""SOSYAL PAKET - yayinlanan/zamanlanan Konsey videolari icin TikTok / Instagram Reels'e KOPYALA-YAPISTIR metni.
Hicbir sey gondermez, hicbir hesaba baglanmaz: operator videoyu kendi hesabindan yukler (TikTok Studio / Reels).

Kullanim:
  python sosyal_paket.py            # son 6 kayit
  python sosyal_paket.py --son 3
  python sosyal_paket.py --id R0NutGxhpy4

Kurallar: kanca cumlesi videodakiyle AYNI (yeni iddia yok), rakam yalniz videodaki; sahte etkilesim/'follow for follow' yok; yapay zeka etiketi hatirlatilir.
"""
import argparse
import json
import os
import re
import sys

import claim_lint
import konsey_konular
import rakam_bankasi

HERE = os.path.dirname(os.path.abspath(__file__))
KAYIT_YOL = os.path.join(HERE, "_engine", "konsey_kayit.jsonl")

ETIKET = {
    "afet": ["#climate", "#sealevel", "#whatif"], "sehir": ["#future", "#cities", "#whatif"],
    "robot": ["#robots", "#ai", "#future"], "uzay": ["#space", "#mars", "#whatif"],
    "insan": ["#future", "#technology", "#whatif"], "son": ["#whatif", "#future", "#thinking"],
    "fizik": ["#science", "#whatif", "#physics"], "gelecek": ["#ai", "#future", "#jobs"],
}
VARSAYILAN = ["#whatif", "#future", "#ai"]
ILK_YORUM = "Team Alpha or Team Beta? Vote below."


def kategori_bul(satir):
    if satir.get("kategori"):
        return satir["kategori"]
    i = rakam_bankasi.konu_id(satir.get("konu", ""))
    k = konsey_konular.konu_bul(i) if i is not None else None
    return (k or {}).get("kategori", "")


def paket(satir):
    """-> dict(aciklama, ilk_yorum, link, uyari). Kanca videodaki kancayla aynidir; etiketler kategoriden."""
    kanca = (satir.get("kanca") or "").strip()
    baslik = (satir.get("baslik") or "").replace("#Shorts", "").strip()
    govde = kanca or baslik
    # Tek basina okununca TEK TARAFLI kalabilecek rakamli kanca ('92 million jobs displaced' yalniz): konunun dengeli kaynakli olgusunu ekle
    if re.search(r"million|billion|%", govde):
        for o in rakam_bankasi.olgular(satir.get("konu", "")):
            if any(rakam_bankasi._sayi_var(n, govde) for n in o["sayilar"]) and len(o["olgu"]) > len(govde):
                govde = f"{govde} {o['olgu']}"
                break
    etiket = ETIKET.get(kategori_bul(satir), VARSAYILAN)
    aciklama = f"{govde} Team Alpha or Team Beta? {' '.join(etiket)} #SignCouncil"
    uyari = [f"{k[0]} ({', '.join(k[1])})" for k in claim_lint.lint(aciklama) if k[0] in claim_lint.BLOCKING]
    return {"aciklama": aciklama, "ilk_yorum": ILK_YORUM, "link": f"https://youtu.be/{satir.get('video_id', '')}",
            "baslik": baslik, "uyari": uyari}


def kayitlar(yol=KAYIT_YOL):
    out = []
    try:
        with open(yol, encoding="utf-8") as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if d.get("video_id"):
                    out.append(d)
    except OSError:
        pass
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="TikTok/Reels icin kopyala-yapistir metni (gondermez)")
    ap.add_argument("--son", type=int, default=6)
    ap.add_argument("--id", default=None, help="tek bir video_id")
    a = ap.parse_args(argv)
    sat = kayitlar()
    if a.id:
        sat = [s for s in sat if s.get("video_id") == a.id]
    else:
        sat = sat[-a.son:]
    if not sat:
        print("Kayit bulunamadi (_engine/konsey_kayit.jsonl).")
        return 2
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for s in sat:
        p = paket(s)
        print(f"\n=== {p['baslik']}  ({p['link']}) ===")
        print(f"TikTok/Reels ACIKLAMASI:\n  {p['aciklama']}")
        print(f"Yayindan sonra ILK YORUM (sabitle):\n  {p['ilk_yorum']}")
        if p["uyari"]:
            print(f"  [UYARI] {', '.join(p['uyari'])}")
    print("\nHatirlatma: TikTok'ta yapay zeka ile uretilmis icerik isaretleme (AI-generated content) secenegini ac; hicbir sahte etkilesim/takip takasi yapma.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
