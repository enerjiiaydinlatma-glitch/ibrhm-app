"""Aura Live (make_video_v2) + hazir paket + panel entegrasyonu birim testi. Calisma dizini = projenin (gecici) kopyasi."""
import importlib.util as u, json, os, subprocess, sys, glob, threading, urllib.request, wave
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:200]))
import growth
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
note = m._render_video(wav, o4, "I am an AI. It got 54 views. Would you watch?", "t2", {"style": "live"})
ck("_render_video: live basarisizsa KLASIGE duser ve nedenini soyler", os.path.exists(o4) and "klasik" in note and "test hatasi" in note, note)
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
