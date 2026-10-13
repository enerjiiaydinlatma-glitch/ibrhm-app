"""SES ANAHTARINI YENILE (Sign Council yerel ses sunucusu :8124 icin; Aura uygulamasinin anahtari AYRIDIR).

  python rotate_voice_key.py              # yeni anahtar uretir, .voice_key'e yazar; eski degeri kodda arar ve YERLERINI soyler
  python rotate_voice_key.py --degistir   # kodda kalan eski anahtar harflerini de YENISIYLA degistirir (son care; kodda acik kalir!)
  python rotate_voice_key.py --kontrol    # sadece tara (degistirmez)

Anahtar degerleri ekrana ASLA yazilmaz. Yenilemeden sonra: Mission Control'u kapatip ac, ses sunucusunu durdurup baslat.
"""
import glob
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(HERE, ".voice_key")


def read_key(path=KEYFILE):
    try:
        return open(path, "rb").read().strip().decode("utf-8")
    except OSError:
        return ""


def new_key():
    return "sc-local-" + secrets.token_urlsafe(24)


def code_files(base):
    pats = ("*.py", "*.bat", "*.ps1", "*.cmd", "*.txt", "*.json", "*.md")
    out = []
    for pat in pats:
        out += glob.glob(os.path.join(base, pat))
    out += glob.glob(os.path.join(base, "studio", "*.js"))
    return [p for p in out if os.path.basename(p) not in (".voice_key",) and "_arsiv" not in p]


def find_literal(base, key):
    """[(dosya, satir_no)] - eski anahtar degerinin birebir gectigi yerler."""
    hits = []
    if not key:
        return hits
    kb = key.encode("utf-8")
    for p in code_files(base):
        try:
            for i, line in enumerate(open(p, "rb").read().splitlines(), 1):
                if kb in line:
                    hits.append((os.path.basename(p), i))
        except OSError:
            pass
    return hits


def rotate(base=HERE, replace=False, keyfile=None):
    keyfile = keyfile or os.path.join(base, ".voice_key")
    old = read_key(keyfile)
    new = new_key()
    leftovers = find_literal(base, old)
    replaced = 0
    if replace and old:
        for fn in {f for f, _ in leftovers}:
            p = os.path.join(base, fn)
            data = open(p, "rb").read()
            open(p, "wb").write(data.replace(old.encode("utf-8"), new.encode("utf-8")))
            replaced += 1
        leftovers = []  # artik yeni anahtar yazili
    with open(keyfile, "wb") as f:
        f.write(new.encode("utf-8") + b"\n")
    return {"had_old": bool(old), "leftovers": leftovers, "replaced_files": replaced, "new_len": len(new)}


def main(argv):
    if "--kontrol" in argv:
        hits = find_literal(HERE, read_key())
        print("Kodda acik kalan anahtar yerleri:", ", ".join(f"{f}:{n}" for f, n in hits) or "yok (temiz)")
        return 1 if hits else 0
    r = rotate(HERE, replace="--degistir" in argv)
    print("[OK] Yeni anahtar .voice_key dosyasina yazildi (degeri gosterilmez).")
    if not r["had_old"]:
        print("[bilgi] Eski .voice_key yoktu.")
    if r["replaced_files"]:
        print(f"[UYARI] {r['replaced_files']} dosyada kodda kalan eski anahtar YENISIYLA degistirildi (acik duruyor; bu dosyalari commit'leme).")
    if r["leftovers"]:
        print("[DIKKAT] Eski anahtar kodda hala yaziyor, bu yerler yeni anahtarla UYUSMAZ:")
        for f, n in r["leftovers"]:
            print(f"   - {f}:{n}")
        print("   Cozum: once  python redact_voice_key.py <dosya>  ile bu dosyalari .voice_key'i okur hale getir,")
        print("   ya da  python rotate_voice_key.py --degistir  (son care).")
    print("\nSimdi: 1) Mission Control'u KAPAT-AC  2) ses sunucusunu durdur/baslat. (Sunucu anahtari baslarken okur.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
