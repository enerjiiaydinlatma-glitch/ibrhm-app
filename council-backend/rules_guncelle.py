"""operator_rules.md - SADECE [PRIORITY] satirini degistirir (operator karari, 8 Ekim 2026).

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


def uygula(yol=YOL, yeni=YENI_PRIORITY, kontrol=False):
    satirlar = _oku(yol)
    idx = [i for i, s in enumerate(satirlar) if s.lstrip().startswith("- [PRIORITY]")]
    if len(idx) != 1:
        return False, f"[PRIORITY] satiri {len(idx)} adet bulundu (1 bekleniyor); dokunulmadi."
    if not any(s.lstrip().startswith("- [LEGAL]") for s in satirlar):
        return False, "[LEGAL] satiri bulunamadi; guvenlik icin dokunulmadi."
    i = idx[0]
    if satirlar[i].strip() == yeni.strip():
        return True, "Zaten guncel."
    if kontrol:
        return True, "ESKI:\n  " + satirlar[i][:300] + " ...\nYENI:\n  " + yeni[:300] + " ..."
    yedek = yol + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(yol, yedek)
    yeni_satirlar = list(satirlar)
    yeni_satirlar[i] = yeni + ("\r" if satirlar[i].endswith("\r") else "")   # CRLF dosyada satir sonu korunur
    # dogrulama: PRIORITY disindaki tum satirlar birebir ayni mi?
    if [s for j, s in enumerate(satirlar) if j != i] != [s for j, s in enumerate(yeni_satirlar) if j != i]:
        return False, "Dogrulama basarisiz; dokunulmadi."
    with open(yol, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(yeni_satirlar))
    return True, f"[PRIORITY] guncellendi. Yedek: {os.path.basename(yedek)} (diger {len(satirlar) - 1} satir degismedi)."


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
