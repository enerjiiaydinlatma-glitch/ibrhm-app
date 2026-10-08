"""SISTEM DURUMU + GUVENLI TEMIZLIK.  Varsayilan: SADECE OKUR (hicbir sey degistirmez).

  python sistem_durumu.py                     # saglik kontrolu + temizlik adaylari raporu
  python sistem_durumu.py --uygula            # adaylari SILMEZ, _arsiv/<tarih>/ altina TASIR (geri alinabilir)
  python sistem_durumu.py --uygula --kategori pycache,log_eski   # sadece secilenler
  python sistem_durumu.py --geri-al 20261008_1530                # tasinanlari yerine koy

Asla dokunmaz: .py/.bat/.ps1 kod dosyalari, receipts/, analysis/, reference_voices/, studio/, danisma/, episodes/,
_engine/predictions.json, mission_token.txt, operator_rules.md, token/anahtar dosyalari, .voice_key, REVIEW_MODE.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
ARSIV = os.path.join(HERE, "_arsiv")
PROTECTED_NAMES = {"predictions.json", "mission_token.txt", "operator_rules.md", "youtube_token.json", "client_secret.json",
                   "youtube_analytics_token.json", ".voice_key", "REVIEW_MODE", ".gitignore", "daily_history.jsonl",
                   "kaynak_son.txt", "plan_history.json"}
PROTECTED_DIRS = {"receipts", "analysis", "reference_voices", "studio", "ney_factory", "danisma", "episodes", "_arsiv", ".git"}


def _age_days(p):
    return (time.time() - os.path.getmtime(p)) / 86400


def _under_protected(path, base=HERE):
    rel = os.path.relpath(path, base).replace("\\", "/").split("/")
    return any(r in PROTECTED_DIRS for r in rel[:-1]) or os.path.basename(path) in PROTECTED_NAMES


def _walk_files(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in PROTECTED_DIRS]
        for f in fn:
            yield os.path.join(dp, f)


# ------------------------------------------------------------------ temizlik adaylari
def cat_pycache(base):
    out = []
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in PROTECTED_DIRS or d == "__pycache__"]
        if os.path.basename(dp) == "__pycache__":
            out += [os.path.join(dp, f) for f in fn]
    return out


def cat_yedek(base):
    return [p for p in _walk_files(base) if re.search(r"\.(bak|tmp|orig)$", p, re.I) and not _under_protected(p, base)]


def cat_log_eski(base, days=14):
    return [p for p in glob.glob(os.path.join(base, "_daily_auto_*.log")) + glob.glob(os.path.join(base, "_gunluk_*.log"))
            if _age_days(p) > days]


def cat_kaynak_paketi_eski(base, days=7):
    return [p for p in glob.glob(os.path.join(base, "_engine", "kaynak_*.json")) if _age_days(p) > days]


def cat_kapak_paketleri(base, days=7):
    d = os.path.join(base, "assets", "thumbnails")
    return [p for p in glob.glob(os.path.join(d, "episode_*")) if os.path.isfile(p) and _age_days(p) > days]


def cat_kisa_ara_dosyalar(base):
    """output/shorts/*/ ara dosyalari: kareler, ses parcalari, birlestirme. Nihai <slug>.mp4/.json KALIR."""
    out = []
    for d in glob.glob(os.path.join(base, "output", "shorts", "*")):
        if not os.path.isdir(d):
            continue
        for p in glob.glob(os.path.join(d, "*")):
            n = os.path.basename(p)
            if re.fullmatch(r"\d\d(_frame(_base|_txt|_mo)?)?\.(png|mp3|mp4)", n) or n in ("_joined.mp4", "_concat.txt"):
                out.append(p)
    return out


def cat_motor_gunleri_eski(base, days=30):
    """_engine/YYYY-MM-DD klasorleri (plan/run kayitlari). Yasi KLASOR ADINDAKI tarihten hesaplanir;
    son 30 gun KALIR (editoryal tekrar kontrolu icin)."""
    out = []
    today = datetime.date.today()
    for d in glob.glob(os.path.join(base, "_engine", "????-??-??")):
        try:
            dt = datetime.date.fromisoformat(os.path.basename(d))
        except ValueError:
            continue
        if os.path.isdir(d) and (today - dt).days > days:
            out.append(d)
    return out


CATEGORIES = {
    "pycache": ("Python onbellegi (__pycache__)", cat_pycache),
    "yedek": ("*.bak / *.tmp / *.orig", cat_yedek),
    "log_eski": ("14 gunden eski gunluk logları", cat_log_eski),
    "kaynak_paketi_eski": ("7 gunden eski kaynak paketleri", cat_kaynak_paketi_eski),
    "kapak_paketleri": ("7 gunden eski A/B kapak paketleri (assets/thumbnails/episode_*)", cat_kapak_paketleri),
    "kisa_ara_dosyalar": ("Short uretim ara dosyalari (kareler, ses parcalari)", cat_kisa_ara_dosyalar),
    "motor_gunleri_eski": ("30 gunden eski _engine/<tarih> klasorleri", cat_motor_gunleri_eski),
}


def size_of(path):
    if os.path.isdir(path):
        return sum(os.path.getsize(f) for f in _walk_files_all(path))
    return os.path.getsize(path) if os.path.exists(path) else 0


def _walk_files_all(root):
    for dp, dn, fn in os.walk(root):
        for f in fn:
            yield os.path.join(dp, f)


def candidates(base=HERE, only=None):
    res = {}
    for k, (desc, fn) in CATEGORIES.items():
        if only and k not in only:
            continue
        items = []
        for p in fn(base):
            if not os.path.exists(p):
                continue
            if k != "pycache" and _under_protected(p, base):
                continue
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in (".py", ".bat", ".ps1") and k != "pycache":
                continue  # kod dosyasi ASLA aday olmaz
            items.append(p)
        res[k] = items
    return res


# ------------------------------------------------------------------ tasima / geri alma
def move_to_archive(items, base=HERE, stamp=None):
    stamp = stamp or datetime.datetime.now().strftime("%Y%m%d_%H%M")
    root = os.path.join(base, "_arsiv", stamp)
    manifest = []
    for p in items:
        rel = os.path.relpath(p, base)
        dst = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(p, dst)
        manifest.append(rel)
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"stamp": stamp, "files": manifest}, f, indent=1)
    return stamp, len(manifest)


def restore(stamp, base=HERE):
    root = os.path.join(base, "_arsiv", stamp)
    m = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    n = 0
    for rel in m["files"]:
        src, dst = os.path.join(root, rel), os.path.join(base, rel)
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            n += 1
    return n


# ------------------------------------------------------------------ saglik kontrolu
def _git(*a):
    try:
        r = subprocess.run(["git", *a], cwd=HERE, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout.strip()
    except Exception as e:
        return 1, str(e)


def health(base=HERE):
    R = []

    def add(ok, name, detail=""):
        R.append(("OK " if ok is True else ("UYARI" if ok is None else "HATA"), name, detail))

    # 1) kod saglam mi
    pys = [p for p in glob.glob(os.path.join(base, "*.py"))]
    bad = []
    for p in pys:
        try:
            compile(open(p, encoding="utf-8", errors="replace").read(), p, "exec")
        except SyntaxError as e:
            bad.append(f"{os.path.basename(p)}:{e.lineno}")
    add(not bad, f"Sozdizimi ({len(pys)} .py)", ", ".join(bad) or "hepsi gecerli")
    # 2) birim testler
    tests = sorted(glob.glob(os.path.join(base, "test_*.py")))
    if tests:
        r = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest"] + [os.path.basename(t)[:-3] for t in tests],
                           cwd=base, capture_output=True, text=True)
        last = (r.stderr.strip().splitlines() or ["?"])[-1]
        add(r.returncode == 0, "Birim testleri", last)
    # 3) gizli anahtar sizintisi (git'te izlenen dosyalar)
    rc, tracked = _git("ls-files", "council-backend")
    leaks = []
    if rc == 0:
        root = os.path.dirname(base)
        for rel in tracked.splitlines():
            fp = os.path.join(root, rel)
            if os.path.isfile(fp) and os.path.splitext(fp)[1].lower() in (".py", ".bat", ".ps1", ".md", ".json", ".txt"):
                try:
                    if re.search(r"sc-local-[A-Za-z0-9_\-]{6,}", open(fp, encoding="utf-8", errors="replace").read()):
                        leaks.append(rel)
                except OSError:
                    pass
        add(not leaks, "Izlenen dosyalarda acik ses anahtari", ", ".join(leaks) or "yok")
    else:
        add(None, "Git denetimi", "git calismadi")
    # 4) dosyalar
    add(os.path.exists(os.path.join(base, ".voice_key")), ".voice_key (ses anahtari yerel dosyasi)")
    gi = os.path.join(base, ".gitignore")
    add(os.path.exists(gi) and ".voice_key" in open(gi, encoding="utf-8", errors="replace").read(), ".gitignore .voice_key iceriyor")
    add(os.path.exists(os.path.join(base, "REVIEW_MODE")), "REVIEW_MODE (zamanli video private cikar)",
        "var" if os.path.exists(os.path.join(base, "REVIEW_MODE")) else "YOK -> zamanlayici acilirsa video HERKESE ACIK cikar")
    for tok in ("youtube_token.json", "client_secret.json"):
        p = os.path.join(base, tok)
        add(os.path.exists(p), tok, (f"son degisim {_age_days(p):.0f} gun once" if os.path.exists(p) else "YOK"))
    # 5) bugunun video sayisi
    day = datetime.date.today().isoformat()
    f = os.path.join(ENGINE if base == HERE else os.path.join(base, "_engine"), day, ".uploaded_today.json")
    cnt = 0
    if os.path.exists(f):
        try:
            sys.path.insert(0, base)
            import daily_limit
            cnt = daily_limit.read_info(f)["count"]
        except Exception:
            cnt = 1
    add(cnt <= 2, f"Bugun yuklenen video ({day})", f"{cnt}/2")
    # 6) ses sunucusu portu
    try:
        with socket.create_connection(("127.0.0.1", 8124), timeout=1):
            add(True, "Ses sunucusu :8124", "acik")
    except OSError:
        add(None, "Ses sunucusu :8124", "kapali (video uretirken acilmali)")
    # 7) git durumu
    rc, br = _git("rev-parse", "--abbrev-ref", "HEAD")
    rc2, ab = _git("rev-list", "--left-right", "--count", "origin/claude/beautiful-archimedes-almi2e...HEAD")
    if rc == 0:
        add(True, f"Git dali: {br}", f"(uzak/yerel fark: {ab})" if rc2 == 0 else "")
    # 8) zamanlanmis gorevler (Windows)
    if os.name == "nt":
        for t in ("SignCouncilDaily", "SignCouncilEvening"):
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-ScheduledTask -TaskName {t}).State"],
                                   capture_output=True, text=True, timeout=30)
                st = r.stdout.strip() or "bulunamadi"
                add(None if st == "Ready" else True, f"Zamanlanmis gorev {t}", st + (" -> otomatik calisir!" if st == "Ready" else ""))
            except Exception as e:
                add(None, f"Zamanlanmis gorev {t}", f"okunamadi: {e}")
    # 9) disk
    try:
        free = shutil.disk_usage(base).free / 1e9
        add(free > 5, "Bos disk", f"{free:.0f} GB")
    except OSError:
        pass
    return R


def fmt_mb(b):
    return f"{b / 1e6:.1f} MB"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="adaylari _arsiv/ altina TASI (silmez)")
    ap.add_argument("--kategori", default="", help="virgullu: " + ",".join(CATEGORIES))
    ap.add_argument("--geri-al", default="")
    ap.add_argument("--hizli", action="store_true", help="testleri/ag kontrollerini atla")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if a.geri_al:
        print(f"{restore(a.geri_al)} dosya yerine konuldu.")
        return 0
    print("=== SAGLIK KONTROLU ===")
    bad = 0
    if not a.hizli:
        for st, name, detail in health():
            print(f"  [{st}] {name}" + (f" - {detail}" if detail else ""))
            bad += st == "HATA"
    only = [k.strip() for k in a.kategori.split(",") if k.strip()] or None
    cands = candidates(HERE, only)
    print("\n=== TEMIZLIK ADAYLARI (silinmez, _arsiv/ altina tasinir) ===")
    total, all_items = 0, []
    for k, items in cands.items():
        sz = sum(size_of(p) for p in items)
        total += sz
        all_items += items
        print(f"  {k:<20} {len(items):>5} oge  {fmt_mb(sz):>10}   {CATEGORIES[k][0]}")
    print(f"  {'TOPLAM':<20} {len(all_items):>5} oge  {fmt_mb(total):>10}")
    scratch = [p for p in glob.glob(os.path.join(HERE, "_*")) if os.path.isfile(p) and os.path.basename(p) not in PROTECTED_NAMES
               and not os.path.basename(p).startswith(("_daily_auto_", "_gunluk_"))]
    if scratch:
        srcs = {p: open(p, encoding="utf-8", errors="replace").read() for p in glob.glob(os.path.join(HERE, "*.py"))}
        print("\n=== INCELE (otomatik tasinmaz; kodda adi geciyorsa SILME) ===")
        for p in sorted(scratch):
            n = os.path.basename(p)
            used = [os.path.basename(f) for f, s in srcs.items() if n in s and os.path.abspath(f) != os.path.abspath(p)]
            print(f"  {n:<32} {fmt_mb(size_of(p)):>8}  " + (f"KODDA GECIYOR: {', '.join(used[:3])}" if used else "kodda gecmiyor (tasinabilir)"))
    if a.uygula:
        if not all_items:
            print("\nTasinacak bir sey yok.")
        else:
            stamp, n = move_to_archive(all_items)
            gi = os.path.join(HERE, ".gitignore")
            cur = open(gi, encoding="utf-8").read() if os.path.exists(gi) else ""
            if "_arsiv/" not in cur.split():
                with open(gi, "a", encoding="utf-8") as f:
                    f.write(("" if cur.endswith("\n") or not cur else "\n") + "_arsiv/\n")
            print(f"\n[OK] {n} oge _arsiv\\{stamp}\\ altina TASINDI. Geri almak icin: python sistem_durumu.py --geri-al {stamp}")
    else:
        print("\n(Bu bir onizleme. Tasimak icin: python sistem_durumu.py --uygula   [--kategori pycache,log_eski])")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
