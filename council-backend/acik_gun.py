"""ACIK GUN - aciklayici (soru -> kaynakli cevap) Short'un PILOTU: senaryo -> kapi -> (senin onayin) -> video. YUKLEME YOK (yukleme duraklatmasi).

Kullanim:
  python acik_gun.py --konu deniz     # How Much Would Sea Level Rise If All the Ice Melted?
  python acik_gun.py --konu robot     # How Many Humanoid Robots Shipped in 2025?
  python acik_gun.py --konu sel       # How Deep Must Flood Water Be To Move a Car?

Karar: Senaryo iyi mi?  evet = uret | s N yeni cumle | e N EKRAN YAZISI | b Yeni Baslik | k YENI KART | hayir = iptal.
Kapidan gecmeyen senaryoda 'tamir modu': satirlari duzelt; kapidan gecene kadar 'evet' kabul edilmez.
Ses sunucusu hazir degilse video URETMEZ. Video hazir olunca oynaticida acilir; hicbir yere YUKLENMEZ.
"""
import argparse
import re
import sys

import acik_format as af
import konsey_format


def goster(r, yaz):
    yaz(f"\nSENARYO (deneme {r['deneme']}):")
    for i, (_w, screen, line, _img) in enumerate(r["beats"], 1):
        yaz(f"  {i}. {screen} | {line}")
    yaz(f"  BASLIK: {r['title']}   KART: {r['hookthumb']}")


def calistir(a, d):
    yaz, gir = d["yaz"], d["gir"]
    if a.konu not in af.ACIK_KONULAR:
        yaz(f"Bilinmeyen konu '{a.konu}'. Secenekler: {', '.join(af.ACIK_KONULAR)}")
        return 2
    yaz(f"\nACIK FORMAT: {af.ACIK_KONULAR[a.konu]['baslik']}\nOLGULAR:\n{af.olgu_metni(a.konu)}")
    d["sunucu_hazirla"]()
    r = af.uret(a.konu, d["llm"], d["parse"])
    gecersiz = not r["ok"]
    for _tur in range(12):
        goster(r, yaz)
        if gecersiz:
            yaz("\nKAPIDAN GECMEDI - video uretilmeyecek:")
            for kod, msg in r["sorunlar"]:
                yaz(f"  - {kod}: {msg}")
            yaz("\n[tamir modu] s N yeni cumle | b Baslik | k KART ile duzelt; kapidan gecene kadar 'evet' KABUL EDILMEZ. hayir = iptal.")
        ham = gir("\nSenaryo iyi mi?  evet = uret | s N yeni cumle | e N EKRAN YAZISI | b Yeni Baslik | k YENI KART | hayir = iptal > ")
        cevap = ham.strip().lower()
        if cevap in ("evet", "e", "yes", "y"):
            if gecersiz:
                yaz("  Senaryo henuz kapidan gecmedi: once sorunlari duzelt.")
                continue
            break
        komut = konsey_format.duzenleme_coz(ham)
        m = re.match(r"^\s*e\s+([1-5])\s+(.+\S)\s*$", ham, re.I | re.S)
        if m:
            komut = ("e", int(m.group(1)), m.group(2))
        if not komut:
            yaz("Iptal edildi. Hicbir sey uretilmedi.")
            return 0
        yeni, sorun = af.duzenle(r, komut)
        if yeni is None:
            yaz("  DEGISIKLIK KAPIDAN GECMEDI (senaryo ayni kaldi):")
            for kod, msg in sorun:
                yaz(f"  - {kod}: {msg}")
        else:
            r, gecersiz = yeni, False
            yaz("  -> degisti.")
    else:
        yaz("Cok fazla tur; iptal.")
        return 0
    if not d["sunucu_bekle"]():
        yaz("\nSes sunucusu (:8124) hazir olmadi - video URETILMEDI (yanlis sesle uretmemek icin). Pencereyi kontrol edip tekrar calistir.")
        return 2
    yaz("\nVideo uretiliyor (~2-3 dk)...")
    meta = d["render"](r, a.konu)
    yaz(f"\nVIDEO HAZIR: {meta['file']}  (~{meta.get('seconds', '?')} sn)")
    d["izle"](meta["file"])
    yaz("  (video oynaticida acildi - izle)\n  YUKLENMEDI (yukleme duraklatmasi). Yayin icin ileride konsey_yukle.py kullanilir.")
    return 0


def _gercek():
    import konsey_gun
    d = konsey_gun._gercek()
    import make_topic_short as mts
    d["render"] = mts.acik_video
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aciklayici Short pilotu (yukleme YOK)")
    ap.add_argument("--konu", required=True, choices=list(af.ACIK_KONULAR))
    a = ap.parse_args(argv)
    if not sys.stdin.isatty():
        print("Etkilesimli terminal gerekli (onay sorulari var).")
        return 2
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return calistir(a, _gercek())


if __name__ == "__main__":
    sys.exit(main())
