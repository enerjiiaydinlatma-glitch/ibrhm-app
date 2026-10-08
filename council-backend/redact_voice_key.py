"""Ses sunucusu anahtarini KODDAN cikarir ve .voice_key dosyasina tasir (.voice_key git'e girmez).

Kullanim (council-backend klasorunde):
  python redact_voice_key.py                 # make_topic_short.py, daily_auto.bat, daily_auto_evening.bat
  python redact_voice_key.py dosya1 dosya2   # belirli dosyalar
  python redact_voice_key.py --check         # sadece tara: acik anahtar kalan dosya var mi (degeri gostermez)

- Anahtarin degeri ekrana YAZILMAZ.
- .py icinde  os.environ.setdefault("AURA_VOICE_KEY", "...")  ->  .voice_key dosyasindan okur
- .bat icinde  set AURA_VOICE_KEY=...  ->  if exist "%~dp0.voice_key" set /p AURA_VOICE_KEY=<"%~dp0.voice_key"
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(HERE, ".voice_key")
DEFAULTS = ["make_topic_short.py", "daily_auto.bat", "daily_auto_evening.bat"]

PY_RE = re.compile(rb'os\.environ\.setdefault\(\s*["\']AURA_VOICE_KEY["\']\s*,\s*["\']([^"\']+)["\']\s*\)')
BAT_RE = re.compile(rb'^[ \t]*set[ \t]+"?AURA_VOICE_KEY=([^\r\n"]+)"?[ \t]*(\r?)$', re.M | re.I)
PY_NEW = (b'os.environ.setdefault("AURA_VOICE_KEY", (open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".voice_key"), '
          b'encoding="utf-8").read().strip() if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".voice_key")) else ""))')
BAT_NEW = b'if exist "%~dp0.voice_key" set /p AURA_VOICE_KEY=<"%~dp0.voice_key"'
LEAK_RE = re.compile(rb'sc-local-[A-Za-z0-9_\-]+')


def redact(path):
    raw = open(path, "rb").read()
    keys = [m.group(1) for m in PY_RE.finditer(raw)] + [m.group(1) for m in BAT_RE.finditer(raw)]
    new = PY_RE.sub(lambda m: PY_NEW, raw)
    new = BAT_RE.sub(lambda m: BAT_NEW + m.group(2), new)
    if new != raw:
        open(path, "wb").write(new)
    return keys, new != raw


def ensure_gitignore():
    gi = os.path.join(HERE, ".gitignore")
    cur = open(gi, encoding="utf-8").read() if os.path.exists(gi) else ""
    if ".voice_key" not in cur.split():
        with open(gi, "a", encoding="utf-8") as f:
            f.write(("" if cur.endswith("\n") or not cur else "\n") + ".voice_key\n")
        return True
    return False


def check():
    bad = []
    for p in glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "*.bat")) + glob.glob(os.path.join(HERE, "*.ps1")):
        if os.path.basename(p) == os.path.basename(__file__):
            continue
        for i, line in enumerate(open(p, "rb").read().splitlines(), 1):
            if LEAK_RE.search(line) or re.search(rb'AURA_VOICE_KEY["\']?\s*[,=]\s*["\']?[A-Za-z0-9_\-]{12,}', line):
                bad.append(f"{os.path.basename(p)}:{i}")
    return bad


def main(argv):
    if argv and argv[0] == "--check":
        bad = check()
        print("ACIK ANAHTAR KALAN YERLER: " + (", ".join(bad) if bad else "yok (temiz)"))
        return 1 if bad else 0
    files = [os.path.join(HERE, f) for f in (argv or DEFAULTS)]
    all_keys = set()
    for f in files:
        if not os.path.exists(f):
            print(f"[atlandi] yok: {os.path.basename(f)}")
            continue
        keys, changed = redact(f)
        all_keys.update(keys)
        print(f"[{'DEGISTI' if changed else 'temiz  '}] {os.path.basename(f)}")
    if len(all_keys) > 1:
        print("[UYARI] dosyalarda birden fazla farkli anahtar bulundu; ilki .voice_key'e yazilir.")
    if all_keys:
        if os.path.exists(KEYFILE) and open(KEYFILE, "rb").read().strip():
            print("[bilgi] .voice_key zaten var, uzerine yazilmadi")
        else:
            open(KEYFILE, "wb").write(sorted(all_keys)[0] + b"\n")
            print("[OK] anahtar .voice_key dosyasina yazildi (degeri gosterilmez)")
    if ensure_gitignore():
        print("[OK] .gitignore'a .voice_key eklendi")
    bad = check()
    print("KONTROL: " + ("acik anahtar kalmadi" if not bad else "HALA ACIK: " + ", ".join(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
