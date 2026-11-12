"""Aura Live (make_video_v2) + hazir paket + panel entegrasyonu birim testi. Calisma dizini = projenin (gecici) kopyasi."""
import importlib.util as u, json, os, subprocess, sys, glob, threading, urllib.request, wave
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:200]))
import growth
import numpy as np
import make_video_v2 as v2

# 1) hazir paketler: gecerli, preflight temiz, kart indeksleri cumle sayisinda
pk = sorted(glob.glob(os.path.join("_studio", "live_packages", "*.json")))
ck("en az bir hazir paket var", len(pk) >= 1, pk)
for fp in pk:
    p = json.load(open(fp, encoding="utf-8"))
    miss = [k for k in ("title", "en_script", "tr_script", "description", "tags", "video_spec") if not p.get(k)]
    ck(f"paket {os.path.basename(fp)}: zorunlu alanlar", not miss, miss)
    r = growth.preflight(p["title"], p["en_script"], p["tr_script"], p["description"], [])
    ck(f"paket {os.path.basename(fp)}: preflight tam ({r['score']}/{r['of']})", r["score"] == r["of"],
       [c["label"] for c in r["checks"] if c["ok"] is False])
    n = len(v2._sentences(p["en_script"]))
    idx = [int(k) for k in (p["video_spec"].get("cards") or {})] + [int(k) for k in (p["video_spec"].get("emotions") or {})]
    ck(f"paket {os.path.basename(fp)}: kart/duygu indeksleri 0..{n-1}", all(0 <= i < n for i in idx), idx)
    ck(f"paket {os.path.basename(fp)}: Ingilizce scriptte Turkce karakter yok", not any(ch in "çğıöşüÇĞİÖŞÜ" for ch in p["en_script"]))

# 2) gercek render (kisa, tek surec): boyut + sure
work = "_vt_work"; os.makedirs(work, exist_ok=True)
wav = os.path.join(work, "a.wav"); out = os.path.join(work, "o.mp4")
v2._synth_demo_audio(wav, sents_n=3, dur=4.0)
v2.make_video_v2(wav, out, "I am an AI. It got 54 views. Would you watch?",
                 {"cards": {"1": {"type": "number", "big": "54", "label": "views"}}, "emotions": {"2": "happy"}},
                 work_dir=work, workers=1)
pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", out],
                    capture_output=True, text=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", out],
                           capture_output=True, text=True).stdout.strip())
ck("v2 render: 1080x1920", pr.stdout.strip() == "1080x1920", pr.stdout)
ck("v2 render: sure ~4 sn", 3.8 <= dur <= 4.3, dur)
ck("v2 render: ses akisi var", "audio" in subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)


# 2b) govdeli karakter (face="bot"): sabit parca onbellegi, boyut, kare uretimi
bs = v2._draw_bot(1.0, 0.5, 1.0, dict(v2.EMO["happy"]), 0.5, 4.0)
ck("bot: 900x1000 RGBA", bs.size == (v2.FW, v2.FH) and bs.mode == "RGBA", bs.size)
ck("bot: kafa/govde dolu (alfa>0 piksel var)", bs.getchannel("A").getbbox() is not None)
wavb = os.path.join(work, "bot.wav"); outb = os.path.join(work, "bot.mp4")
v2._synth_demo_audio(wavb, sents_n=2, dur=3.0)
v2.make_video_v2(wavb, outb, "I got a body. Which look do you like?", {"face": "bot", "cards": {"1": {"type": "number", "big": "A", "label": "x", "static": True}}}, work_dir=work, workers=1)
prb = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", outb], capture_output=True, text=True)
ck("bot render: 1080x1920", prb.stdout.strip() == "1080x1920", prb.stdout)


# 2c) 3B insansi robot (face="robot"): sprite varliklari, vizor yuz haritasi, kare uretimi
rb = v2._draw_robot(1.0, 0.5, 1.0, dict(v2.EMO["happy"]), 0.5, 0, (1.0, 0.0, 0.0))
ck("robot: sprite 1080x1190 RGBA", rb.size == (1080, 1190) and rb.mode == "RGBA", rb.size)
ck("robot: vizor haritasi bos degil", v2._ROBOT["p0"]["mask"].sum() > 5000, v2._ROBOT["p0"]["mask"].sum())
ck("robot: yuz vizore basildi (govde+yuz farkli)", np.asarray(rb.convert("RGB")).astype(int).sum() != np.asarray(v2._ROBOT["p0"]["base"].convert("RGB")).astype(int).sum())
wavr = os.path.join(work, "robot.wav"); outr = os.path.join(work, "robot.mp4")
v2._synth_demo_audio(wavr, sents_n=2, dur=3.0)
v2.make_video_v2(wavr, outr, "I got a body. Which look do you like?", {"face": "robot", "poses": {"0": "p1"}, "cards": {"1": {"type": "number", "big": "A", "label": "x", "static": True}}}, work_dir=work, workers=1)
prr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", outr], capture_output=True, text=True)
ck("robot render: 1080x1920", prr.stdout.strip() == "1080x1920", prr.stdout)


# 2d) 3B sahne (scene3d): plan mantigi, homografi, yuz izgara yerlestirme; klipler hazirsa uctan uca render
import scene3d
tl_t = [("a", 0.0, 3.0), ("b", 3.0, 3.0), ("c", 6.0, 3.0), ("d", 9.0, 3.0), ("e", 12.0, 3.0), ("f", 15.0, 3.0)]
nf_t = 18 * 30
pl = scene3d.build_plan(nf_t, tl_t, {3: {"type": "number"}}, ["happy", "neutral", "sad", "neutral", "neutral", "neutral"], {"intro": True})
ck("plan: her kare icin bir (klip, no)", len(pl) == nf_t and all(c in scene3d.CLIP_N and 0 <= k < scene3d.CLIP_N[c] for c, k in pl))
ck("plan: intro ile basliyor", pl[0] == ("intro", 0) and pl[137][0] == "intro")
ck("plan: kart onunde to_C, kartta idle_C/point_C, sonra to_M", pl[9 * 30 - 5][0] == "to_C" and pl[9 * 30 + 20][0] in ("idle_C", "point_C") and any(c == "to_M" for c, _ in pl[12 * 30 - 25:12 * 30]))
ck("plan: jest (sad -> shrug_M)", any(c == "shrug_M" for c, _ in pl))
pl2 = scene3d.build_plan(nf_t, tl_t, {1: {"type": "number"}}, ["neutral"] * 6, {"intro": True})
ck("plan: kart erken ise intro atlanir", pl2[0][0] != "intro")
co = scene3d._homography([(0, 0), (100, 0), (100, 80), (0, 80)], [(10, 10), (60, 10), (60, 50), (10, 50)])
x0, y0 = 100, 80
den = co[6] * x0 + co[7] * y0 + 1
ck("homografi: kose eslesmesi", abs((co[0] * x0 + co[1] * y0 + co[2]) / den - 60) < 1e-6 and abs((co[3] * x0 + co[4] * y0 + co[5]) / den - 50) < 1e-6)
from PIL import Image as _I
N_ = 5
tex_ = _I.new("RGBA", (scene3d.TW, scene3d.TH), (255, 255, 255, 255))
pts_ = [[200 + i * 20, 300 + j * 18] for j in range(N_ + 1) for i in range(N_ + 1)]
fr_ = np.zeros((600, 600, 3), np.uint8)
mk_ = np.full((600, 600), 255, np.uint8)
out_ = scene3d.draw_face(fr_, mk_, pts_, [1.0] * ((N_ + 1) ** 2), tex_, N_)
ck("yuz izgarasi: vizor bolgesine isik basilir", out_[300:390, 200:300].mean() > 100 and out_[0:100, 0:100].max() == 0, out_[300:390, 200:300].mean())
if scene3d.set_complete("studio"):
    outs = os.path.join(work, "s3d.mp4"); wavs = os.path.join(work, "s3d.wav")
    v2._synth_demo_audio(wavs, sents_n=3, dur=8.0)
    v2.make_video_v2(wavs, outs, "I walk in. Here is a number. Then I shrug.", {"face": "scene3d", "set": "studio", "cards": {"1": {"type": "number", "big": "7", "label": "x", "static": True}}}, work_dir=work, workers=2)
    prs = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", outs], capture_output=True, text=True)
    ck("scene3d render: 1080x1920", prs.stdout.strip() == "1080x1920", prs.stdout)
else:
    ck("scene3d klipleri yok -> uctan uca atlandi (robot'a dusme)", True)

# 3) coklu islemci yolu (en az 120 kare gerekir): 5 sn
wav2 = os.path.join(work, "b.wav"); out2 = os.path.join(work, "o2.mp4")
v2._synth_demo_audio(wav2, sents_n=2, dur=5.0)
v2.make_video_v2(wav2, out2, "Two subscribers. Real numbers only.", {}, work_dir=work, workers=2)
d2 = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", out2], capture_output=True, text=True).stdout.strip())
ck("v2 coklu islemci render: ~5 sn", 4.8 <= d2 <= 5.3, d2)

# 4) panel: _render_video secimi + yedek (klasige dusme) + paket yukleme
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
m._safe_channel_titles = lambda: []
o3 = os.path.join(work, "o3.mp4")
note = m._render_video(wav, o3, "I am an AI. It got 54 views. Would you watch?", "t1", {"style": "live"})
ck("_render_video live: not bos, dosya var", note == "" and os.path.exists(o3), note)
orig = v2.make_video_v2
def boom(*a, **k): raise RuntimeError("test hatasi")
v2.make_video_v2 = boom
o4 = os.path.join(work, "o4.mp4")
try:
    m._render_video(wav, o4, "I am an AI. It got 54 views. Would you watch?", "t2", {"style": "live"})
    raised = ""
except RuntimeError as e:
    raised = str(e)
ck("_render_video: live basarisizsa DURUR (sessiz klasik yok), nedeni soyler", (not os.path.exists(o4)) and "test hatasi" in raised and "URETILMEDI" in raised, raised)
note = m._render_video(wav, o4, "I am an AI. It got 54 views. Would you watch?", "t2", {"style": "live", "allow_classic": True})
ck("_render_video: allow_classic ile bilincli klasik yedek", os.path.exists(o4) and "klasik" in note and "test hatasi" in note, note)
v2.make_video_v2 = orig
o5 = os.path.join(work, "o5.mp4")
note = m._render_video(wav, o5, "I am an AI. It got 54 views. Would you watch?", "t3", None)
ck("_render_video: spec yoksa klasik (varsayilan degismedi)", os.path.exists(o5) and note == "")
r1 = m._growth_load_packages()
r2 = m._growth_load_packages()
dr = growth.drafts_list()
ck("paket yukleme: ilk cagrida taslak eklenir, video_spec korunur", r1["ok"] and len(r1["added"]) == len(pk) and all(d.get("video_spec") for d in dr), (r1, [d.get("video_spec") is not None for d in dr]))
ck("paket yukleme: ikinci cagri mukerrer eklemez", r2["added"] == [] and len(r2["skipped"]) == len(pk), r2)
ck("paket yukleme: taslaklar YAYINLANMAMIS", all(d["status"] == "taslak" for d in dr), [d["status"] for d in dr])

# 4b) cok-planli kurgu (autocut / cutaway) + seri bandi
import scene3d
tl_t = [("s%d." % i, i * 2.0, 2.0) for i in range(8)]
sp_t = {"set": "studio", "intro": False, "autocut": True, "cutaway_sets": ["cern"], "auto_gestures": False, "point": False}
pl = scene3d.build_plan(480, tl_t, {5: 1}, ["neutral"] * 8, sp_t)
names = sorted(set(c for c, _ in pl))
ck("autocut: planlar C ve M arasinda degisir", "idle_C" in names and "idle_M" in names, names)
ck("autocut: cutaway set klibi plana girer", any(n.startswith("cern:") for n in names), names)
ck("autocut: kart penceresi bozulmaz (cumle 5 -> to_C/idle_C/to_M)", any(pl[f][0] in ("to_C", "idle_C") for f in range(int(5 * 2.0 * 30), int(6 * 2.0 * 30))), "")
ck("autocut: kapaliysa klasik plan", set(c for c, _ in scene3d.build_plan(480, tl_t, {5: 1}, ["neutral"] * 8, dict(sp_t, autocut=False))) <= {"idle_M", "idle_C", "to_C", "to_M", "point_C", "nod_M", "shrug_M", "intro"}, "")
txt8 = " ".join(["This is sentence number %d." % i for i in range(8)])
wav8 = os.path.join(work, "c8.wav")
m_v2 = __import__("make_video_v2")
m_v2._synth_demo_audio(wav8, sents_n=8)
out8 = os.path.join(work, "c8.mp4")
m_v2.make_video_v2(wav8, out8, txt8, {"style": "live", "face": "scene3d", "set": "studio", "intro": False, "autocut": True, "cutaway_sets": ["cern"], "series": "AURA WORLD TOUR  -  STOP 4", "cards": {"3": {"type": "number", "big": "5", "label": "test"}}}, sfx=False)
ck("autocut+seri bandi: render tamam", os.path.exists(out8) and os.path.getsize(out8) > 50000, os.path.getsize(out8) if os.path.exists(out8) else 0)

# 4c) hook kaplamasi (ilk ~2 sn buyuk yazi): ilk karelerde gorunur, sonra kaybolur
import subprocess as _sp
out9 = os.path.join(work, "hook.mp4")
m_v2.make_video_v2(wav8, out9, txt8, {"style": "live", "face": "scene3d", "set": "studio", "intro": True, "hook": {"big": "UNDER 6 YEARS", "label": "test", "secs": 1.5}}, sfx=False)
def _fr(path, ts):
    r = _sp.run(["ffmpeg", "-v", "error", "-ss", str(ts), "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-vf", "crop=900:300:90:230,scale=90:30", "-"], capture_output=True)
    return list(r.stdout)
a1, a2 = _fr(out9, 0.8), _fr(out9, 3.0)
ck("hook kaplamasi: ilk saniyede gorunur, sonra kaybolur", len(a1) == 2700 and len(a2) == 2700 and sum(abs(x - y) for x, y in zip(a1, a2)) > 20000, (sum(abs(x - y) for x, y in zip(a1, a2)) if len(a1) == len(a2) else -1))

# 5) GERCEK HTTP yonlendirme
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
req = urllib.request.Request(f"http://127.0.0.1:{port}/api/growth/load_packages", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
try:
    r = urllib.request.urlopen(req, timeout=30); c, j = r.status, json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    c, j = e.code, None
ck("HTTP POST /api/growth/load_packages: 200 + JSON", c == 200 and j and j.get("ok") is True, (c, j))
srv.shutdown()
print(json.dumps({"total": len(res), "bad": [(n, dd) for n, o, dd in res if not o]}, ensure_ascii=False))
