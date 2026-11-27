"""temizle.py: liste modu hicbir sey silmez; --sil yalniz bilinen kalintilari siler; veri/yayin dosyalarina ASLA dokunmaz."""
import importlib.util as u, json, os, sys, tempfile, time
s = u.spec_from_file_location("temizle", "temizle.py"); t = u.module_from_spec(s); s.loader.exec_module(t)
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
root = tempfile.mkdtemp(); tmp = tempfile.mkdtemp()
def mk(rel, data=b"x", age_days=0):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data)
    if age_days: os.utime(p, (time.time() - age_days * 86400,) * 2)
    return p
keep = [mk("_studio/day_status.json", b"{}"), mk("_studio/token.json"), mk("_studio/access_token.txt"), mk("_studio/code_pin.txt"), mk("_studio/output/aura_a.mp4"),
        mk("_studio/uploads/x.png"), mk("_studio/live_packages/tour_007.json"), mk("_studio/assets/a.mp4"), mk("aura_studio.py"), mk("_studio/_backups/yeni.bak", age_days=2),
        mk("_studio/tiktok_stats.json")]
gone = [mk("__pycache__/a.pyc"), mk("_studio/__pycache__/b.cpython-312.pyc"), mk("_studio/_video_work/x_raw.wav"), mk("_studio/_video_work/_v2_seg0.mp4"),
        mk("_studio/_panel_run_log.txt"), mk("_studio/_pub_desc_tmp.txt"), mk("_studio/_backups/eski.bak", age_days=45)]
bat = os.path.join(tmp, "aura_guncelle_run.bat"); open(bat, "w").write("x"); gone.append(bat)
lines = []
code = t.main([], root=root, temp=tmp, out=lambda *a: lines.append(" ".join(map(str, a))))
ck("liste modu: hicbir dosyayi SILMEZ", code == 0 and all(os.path.exists(p) for p in keep + gone) and "Hicbir sey silinmedi" in "\n".join(lines), "\n".join(lines)[-200:])
ck("liste modu kategorileri ve toplami gosterir", "TOPLAM" in "\n".join(lines) and "__pycache__" in "\n".join(lines))
t.main(["--sil"], root=root, temp=tmp, out=lambda *a: lines.append(" ".join(map(str, a))))
ck("--sil: kalintilar silindi", not any(os.path.exists(p) for p in gone), [p for p in gone if os.path.exists(p)])
ck("--sil: veri, token, PIN, yayin videosu, yukleme, paket, asset, kod, yeni yedek DURUYOR", all(os.path.exists(p) for p in keep), [p for p in keep if not os.path.exists(p)])
lines2 = []
t.main([], root=root, temp=tmp, out=lambda *a: lines2.append(" ".join(map(str, a))))
ck("ikinci calistirma: temizlenecek bir sey kalmadi", "Temizlenecek bir sey yok" in "\n".join(lines2) or "TOPLAM" not in "\n".join(lines2), lines2)
bad = [n for n, ok, d in res if not ok]
for n, ok, d in res: print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
sys.exit(1 if bad else 0)
