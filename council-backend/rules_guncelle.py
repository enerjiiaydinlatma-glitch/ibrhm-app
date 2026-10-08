"""operator_rules.md - SADECE iki degisiklik (operator karari, 8 Ekim 2026):
  1) [PRIORITY] satiri yeniden yazilir (birincil kriter -> bonus)
  2) [FORMAT] satirinda "alarming" -> "surprising" (yalniz bu kelime)

Guvenlik: degisiklikten once yedek; baska HICBIR satir degismez (kontrol edilir); [LEGAL] satiri mutlaka korunur.
Kullanim:
  python rules_guncelle.py            -> yedek al + PRIORITY'yi yeni metinle degistir
  python rules_guncelle.py --kontrol  -> sadece neyin degisecegini goster
  python rules_guncelle.py --geri-al  -> en son yedegi geri yukle
"""
import argparse
import datetime
import glob
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
YOL = os.path.join(HERE, "_engine", "operator_rules.md")

YENI_PRIORITY = (
    "- [PRIORITY] 8 Ekim 2026 operator karari (2 Ekim konsey kararinin YENIDEN DUZENLENMESI): konu secimini once IZLEYICI ILGISI ve "
    "sade anlatilabilirlik belirler. Kamuya acik bir belgeyle KANITLANABILEN bir cikar catismasi (bir kurulus kendi urununu kendi "
    "notluyor/denetliyor/kurallarini kendi koyuyor) varsa bu guclu bir BONUS aci olabilir (tek ornekte en iyi abone donusumu: "
    "165 izlenmede 3 abone, tutma %31.7) - ama ZORUNLU DEGIL ve birincil kriter DEGIL; kanitlayacak bir belge yoksa bu aciyi zorlama, "
    "baska bir konuya gec. Sunum: iddiayi KANITLA - metodolojiyi ve sinirlamalarini acikca soyle (Beta), sansasyonel duyum degil "
    "kamuya acik belgedeki celiskiyi goster (Delta). Niyet atfi ve suc dili YASAK (LEGAL kurali aynen gecerli). Bu satirdaki rakamlar "
    "tek video orneginden gelir: kanit degil yondur; sutunlarin (ikilem / siralama / receipt / aciklayici) gercek sonuclari kanalin "
    "kendi verisiyle olculur."
)


def _oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:      # newline="": CRLF/LF aynen korunur
        return f.read().split("\n")


def _bul(satirlar, etiket):
    return [i for i, s in enumerate(satirlar) if s.lstrip().startswith(etiket)]


def uygula(yol=YOL, yeni=YENI_PRIORITY, kontrol=False):
    satirlar = _oku(yol)
    pi = _bul(satirlar, "- [PRIORITY]")
    if len(pi) != 1:
        return False, f"[PRIORITY] satiri {len(pi)} adet bulundu (1 bekleniyor); dokunulmadi."
    if not _bul(satirlar, "- [LEGAL]"):
        return False, "[LEGAL] satiri bulunamadi; guvenlik icin dokunulmadi."
    fi = _bul(satirlar, "- [FORMAT]")
    if len(fi) > 1:
        return False, f"[FORMAT] satiri {len(fi)} adet bulundu (en fazla 1 bekleniyor); dokunulmadi."
    yeni_satirlar = list(satirlar)
    degisen = []
    i = pi[0]
    yeni_p = yeni + ("\r" if satirlar[i].endswith("\r") else "")    # CRLF dosyada satir sonu korunur
    if satirlar[i].strip() != yeni.strip():
        yeni_satirlar[i] = yeni_p
        degisen.append("PRIORITY")
    if fi:
        j = fi[0]
        if "alarming" in satirlar[j]:
            yeni_satirlar[j] = satirlar[j].replace("alarming", "surprising")
            degisen.append("FORMAT (alarming -> surprising)")
    if not degisen:
        return True, "Zaten guncel."
    if kontrol:
        ozet = []
        if "PRIORITY" in degisen:
            ozet.append("[PRIORITY] ESKI:\n  " + satirlar[i][:200] + " ...\n[PRIORITY] YENI:\n  " + yeni[:200] + " ...")
        if fi and len(degisen) and any(d.startswith("FORMAT") for d in degisen):
            ozet.append(f"[FORMAT] 'alarming' {satirlar[fi[0]].count('alarming')} yerde 'surprising' olacak.")
        return True, "\n".join(ozet)
    yedek = yol + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(yol, yedek)
    dokunulan = {k for k in (i, fi[0] if fi else -1) if yeni_satirlar[k] != satirlar[k]} if fi else {i}
    # dogrulama: degisenler disindaki tum satirlar birebir ayni mi? satir sayisi ayni mi?
    if len(satirlar) != len(yeni_satirlar) or any(
            a != b for k, (a, b) in enumerate(zip(satirlar, yeni_satirlar)) if k not in dokunulan):
        return False, "Dogrulama basarisiz; dokunulmadi."
    with open(yol, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(yeni_satirlar))
    return True, f"Guncellendi: {', '.join(degisen)}. Yedek: {os.path.basename(yedek)} (diger satirlar degismedi)."


def geri_al(yol=YOL):
    yedekler = sorted(glob.glob(yol + ".bak_*"))
    if not yedekler:
        return False, "Yedek bulunamadi."
    shutil.copy2(yedekler[-1], yol)
    return True, f"Geri yuklendi: {os.path.basename(yedekler[-1])}"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--kontrol", action="store_true")
    ap.add_argument("--geri-al", action="store_true", dest="geri")
    a = ap.parse_args()
    if not os.path.exists(YOL):
        print("operator_rules.md bulunamadi:", YOL)
        sys.exit(1)
    ok, msg = geri_al() if a.geri else uygula(kontrol=a.kontrol)
    print(("[OK] " if ok else "[HATA] ") + msg)
    sys.exit(0 if ok else 1)
