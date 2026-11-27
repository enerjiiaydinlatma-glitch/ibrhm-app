"""Sistem taramasi: ses (basta sessizlik/seviye/kelime-sn), ilk kare istatistigi + kontak sayfasi, kanca karsilastirmasi, konsey 'scan' modu (gorsel + metin)."""
import importlib.util as u, json, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
import scan
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
import growth
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
tmp = tempfile.mkdtemp()
vid = os.path.join(tmp, "aura_scantest.mp4")
# 6 sn: ilk 1 sn SESSIZ, sonra ton; gorsel: test deseni
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=30:duration=6", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                "-af", "adelay=1000|1000,apad", "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", vid], check=True)
a = scan.audio_stats(vid)
ck("ses: basta sessizlik ~1 sn bulunur", a["lead_silence_s"] is not None and 0.8 <= a["lead_silence_s"] <= 1.3, a)
ck("ses: ortalama/tepe seviye dolu", a["mean_db"] is not None and a["max_db"] is not None, a)
ck("sure okunur", abs(scan.duration(vid) - 6) < 0.3, scan.duration(vid))
fp = scan.extract_frame(vid, 0.3, os.path.join(tmp, "f.jpg"))
fs = scan.frame_stats(fp)
ck("ilk kare: parlaklik/kontrast/renk yayilimi hesaplanir", fs["brightness"] > 0 and fs["contrast"] > 0 and fs["color_spread"] > 0, fs)
sheet = scan.contact_sheet([("test", fp), ("yok", os.path.join(tmp, "olmayan.jpg"))])
ck("kontak sayfasi: gecerli JPEG (base64), olmayan kare atlanir", sheet and __import__("base64").b64decode(sheet)[:2] == b"\xff\xd8")
ck("ilk cumle ayristirma", scan.first_sentence("Who hid inside Derinkuyu? I'm Aura.") == "Who hid inside Derinkuyu?")
rows = []
for i, (fs_, v, p) in enumerate([("Who hid here?", 40, 50), ("Why did it fall?", 60, 45), ("Come inside CERN with me.", 118, 30), ("Come inside Vostok with me.", 17, 39), ("The Great Pyramid has 2.3 million blocks.", 9, 19), ("Stonehenge stones came from 150 miles.", 47, 60)]):
    h = scan.hook_row("T%d" % i, fs_); h["views"], h["avg_pct"] = v, p; rows.append(h)
f = scan.hook_findings(rows)
ck("kanca: soru / rakam / davet gruplari karsilastirilir", any("SORU" in x and "n=2" in x for x in f) and any("RAKAM" in x for x in f) and any("Come inside" in x for x in f), f)
ck("kanca: az veride 'yeterli veri yok' der (uydurma yok)", any("yeterli veri yok" in x for x in scan.hook_findings(rows[:2])))
sf = scan.voice_findings([{"wps": 2.8, "lead_silence_s": 1.0, "mean_db": -20.0}, {"wps": 3.0, "lead_silence_s": 0.0, "mean_db": -22.0}])
ck("ses bulgulari: hiz + bastaki sessizlik uyarisi + seviye", any("kelime/sn" in x for x in sf) and any("kanca icin riskli" in x for x in sf), sf)
# tam rapor + _scan_run
os.makedirs(m.OUTPUT_DIR, exist_ok=True)
slug = "aura_" + __import__("re").sub(r"[^a-z0-9]+", "", "Scan Test Video".lower())[:24] + ".mp4"
dst = os.path.join(m.OUTPUT_DIR, slug)
import shutil; shutil.copy2(vid, dst)
growth.drafts_list = lambda: [{"id": "x", "title": "Scan Test Video", "en_script": "Who hid here? One two three four five six seven eight.", "created": "2026-11-27 10:00"}]
m._measure_state = lambda: {"rows": [{"title": "Scan Test Video", "views": 30, "avg_pct": 41.0, "likes": 1, "comments": 0, "tt_views": 120, "tt_shares": 0}]}
rep = m._scan_run(force=True)
os.remove(dst)
ck("_scan_run: 1 video, 4 boyut, kontak sayfasi", rep["n_videos"] == 1 and set(rep["dims"]) == {"kanca", "ses", "ilk_gorsel", "etkilesim"} and rep["sheet_b64"], list(rep["dims"]))
ck("etkilesim ozeti gercek sayilardan", "30 izlenme" in rep["dims"]["etkilesim"]["findings"][0], rep["dims"]["etkilesim"]["findings"])
seen = {}
def mk(name):
    def fn(messages, system, timeout=45):
        seen[name] = (messages, system); return "ok"
    return fn
orig = {n: ok for n, ok, fn in m.COUNCIL_MEMBERS}
ck("konsey uyeleri: 5 ana + opsiyonel Perplexity/DeepSeek/Mistral kayitli", {"Gemini", "Anthropic", "OpenAI", "Grok", "Groq", "Perplexity", "DeepSeek", "Mistral"} <= set(orig), list(orig))
ck("ek saglayicilar ANAHTARSIZ katilmaz", not orig["Perplexity"]() and not orig["DeepSeek"]() and not orig["Mistral"](), "")
os.environ["PERPLEXITY_API_KEY"] = "x"
ck("anahtar ortama konunca otomatik katilir", orig["Perplexity"]())
del os.environ["PERPLEXITY_API_KEY"]
m.COUNCIL_MEMBERS = [("Gemini", lambda: True, mk("Gemini")), ("Groq", lambda: True, mk("Groq"))]
m._ai_usage_add = lambda *a, **k: None
m._measure_state = lambda: {"subs": 2, "total_views": 5, "median_views": 1, "week_views": 1, "rows": []}
m._scan_run = lambda force=False: rep
r = m._council_run("scan", "")
msg = seen["Gemini"][0][0]
ck("konsey 'scan': metin + kontak sayfasi gorseli gider", r["ok"] and "AUTOMATIC SCAN" in msg["content"] and msg.get("image_b64") and msg["image_mime"] == "image/jpeg", list(msg))
ck("konsey 'scan' istemi 6 boyut ister", all(w in seen["Gemini"][1] for w in ("HOOK", "VOICE", "FIRST VISUAL", "INTERACTION", "TOPIC", "INTERFACE")))
bad = [n for n, ok, d in res if not ok]
for n, ok, d in res: print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
sys.exit(1 if bad else 0)
