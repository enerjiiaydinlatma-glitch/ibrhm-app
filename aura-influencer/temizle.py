"""Eski kalintilari temizler (VARSAYILAN: sadece LISTELER, hicbir sey silmez).

    python temizle.py          # ne silinecegini ve boyutlarini gosterir
    python temizle.py --sil    # listelenenleri siler

SILER (hepsi kendiliginden yeniden uretilir): __pycache__/ *.pyc, _studio/_video_work/ icindeki 7 günden eski gecici render dosyalari (son 7 gun kalir),
_studio/ altindaki _*_log.txt ve _pub_desc_tmp.txt, _studio/_backups icinde 30 günden eski yedekler, %TEMP%\\aura_guncelle_run.bat.
ASLA DOKUNMAZ: *.json verileri, output/ (yayin videolari), uploads/, token/anahtar/PIN dosyalari, assets/, live_packages/, kod.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
LOGS = ("_panel_run_log.txt", "_tunnel_log.txt", "_safe_restart_log.txt", "_voice_mesh_restart_log.txt", "_pub_desc_tmp.txt")


def _inside(root, p):
    root, p = os.path.realpath(root), os.path.realpath(p)
    return p == root or p.startswith(root + os.sep)


def collect(root=ROOT, temp=None, now=None, backup_days=30):
    now = now or time.time()
    items = []          # (kategori, yol)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", "node_modules", "output", "uploads", "assets", "live_packages")]
        for d in list(dns):
            if d == "__pycache__":
                items.append(("__pycache__", os.path.join(dp, d)))
                dns.remove(d)
        for f in fns:
            if f.endswith(".pyc"):
                items.append(("__pycache__", os.path.join(dp, f)))
    vw = os.path.join(root, "_studio", "_video_work")
    if os.path.isdir(vw):
        for f in os.listdir(vw):
            pth = os.path.join(vw, f)
            if now - os.path.getmtime(pth) > 7 * 86400:        # son 7 gunun ham sesi kalir (Turkce altyazi gerekirse yeniden uretilebilsin)
                items.append(("gecici render dosyasi (7+ gun)", pth))
    for f in LOGS:
        p = os.path.join(root, "_studio", f)
        if os.path.isfile(p):
            items.append(("log/gecici", p))
    bk = os.path.join(root, "_studio", "_backups")
    if os.path.isdir(bk):
        for dp, _, fns in os.walk(bk):
            for f in fns:
                p = os.path.join(dp, f)
                if now - os.path.getmtime(p) > backup_days * 86400:
                    items.append((f"yedek ({backup_days}+ gun)", p))
    t = temp if temp is not None else os.environ.get("TEMP")
    if t:
        p = os.path.join(t, "aura_guncelle_run.bat")
        if os.path.isfile(p):
            items.append(("guncelle gecici kopya", p))
    return items


def size_of(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    n = 0
    for dp, _, fns in os.walk(p):
        for f in fns:
            try:
                n += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return n


def delete(p):
    import shutil
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p)
    else:
        os.remove(p)


def main(argv, root=ROOT, temp=None, out=print):
    do = "--sil" in argv
    items = collect(root, temp)
    if not items:
        out("Temizlenecek bir sey yok.")
        return 0
    total = 0
    cats = {}
    for cat, p in items:
        sz = size_of(p)
        total += sz
        cats.setdefault(cat, [0, 0])
        cats[cat][0] += 1
        cats[cat][1] += sz
    for cat, (n, sz) in cats.items():
        out("  %-28s %4d oge  %8.1f KB" % (cat, n, sz / 1024))
    out("  %-28s %4d oge  %8.1f KB" % ("TOPLAM", len(items), total / 1024))
    if not do:
        out("\nHicbir sey silinmedi (liste modu). Silmek icin: python temizle.py --sil")
        return 0
    ok = bad = 0
    for cat, p in items:
        if not (_inside(root, p) or (temp is not None and _inside(temp, p)) or os.path.basename(p) == "aura_guncelle_run.bat"):
            bad += 1
            continue
        try:
            delete(p)
            ok += 1
        except OSError as e:
            bad += 1
            out("  atlandi (kullanimda olabilir): %s (%s)" % (p, e.__class__.__name__))
    out("\nSilindi: %d, atlandi: %d" % (ok, bad))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
