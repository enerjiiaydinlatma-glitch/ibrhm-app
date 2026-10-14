"""Uzun video yapicisi birim testi: script kurallari, kartlar, GERCEK HTTP uzerinden render/yayin akisi (ses ve yayin betigi sahte)."""
import copy, importlib.util as u, json, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:220]))
import make_longform as ml
SCRIPT = json.load(open(os.path.join("_studio", "longform", "scoreboard_001.json"), encoding="utf-8"))
def blockers(sc): return [l for ok, l, d in ml.check_script(sc) if ok is False]

# --- kurallar
ck("gercek senaryo: engel yok", blockers(SCRIPT) == [], blockers(SCRIPT))
def mut(fn):
    sc = copy.deepcopy(SCRIPT); fn(sc); return blockers(sc)
ev = lambda sc: next(s for s in sc["scenes"] if s["kind"] == "evidence")
ck("kaynaksiz kanit cumlesi reddedilir", any("KAYNAK" in b for b in mut(lambda sc: ev(sc)["sentences"][0].pop("source"))))
ck("TR karsiligi eksik reddedilir", any("TR karsiligi" in b for b in mut(lambda sc: ev(sc)["sentences"][0].update(tr=""))))
ck("EN'de Turkce karakter reddedilir", any("Turkce karakter" in b for b in mut(lambda sc: ev(sc)["sentences"][0].update(en="Bu cümle Türkçe"))))
ck("skor tablosu kararlarla uyusmazsa reddedilir", any("Skor tablosu" in b for b in mut(lambda sc: next(s for s in sc["scenes"] if s["kind"] == "scoreboard").update(rows_verdicts=["REAL", "REAL", "REAL", "REAL"]))))
ck("karar sizintisi (kanit sahnesinde 'Verdict: hype.') reddedilir", any("Karar cumlesi" in b for b in mut(lambda sc: ev(sc)["sentences"].insert(0, {"en": "Verdict: hype.", "tr": "Karar: abarti.", "source": "x"}))))
ck("'what would change' cumlesi yoksa reddedilir", any("degistirir" in b for b in mut(lambda sc: ev(sc).update(sentences=[x for x in ev(sc)["sentences"] if x.get("role") != "change"]))))
ck("3'ten az kaynakli kanit reddedilir", any("en az 3" in b for b in mut(lambda sc: ev(sc).update(sentences=ev(sc)["sentences"][:2] + [x for x in ev(sc)["sentences"] if x.get("role")]))))
ck("Outro'da Follow cumlesi yoksa reddedilir", any("Follow" in b for b in mut(lambda sc: sc["scenes"][-1].update(sentences=sc["scenes"][-1]["sentences"][:2]))))
ck("gecersiz karar reddedilir", any("REAL / HYPE" in b for b in mut(lambda sc: next(s for s in sc["scenes"] if s["kind"] == "verdict").update(verdict="MAYBE"))))
ck("abartili vaat ('guarantee') reddedilir", any("Abartili" in b for b in mut(lambda sc: sc["scenes"][0]["sentences"][0].update(en="We guarantee this is true."))))

# --- bolumler (YouTube kurali: 0:00'dan baslar, >=3, aralik >=10 sn)
starts = []; t = 0.0
for sc in SCRIPT["scenes"]:
    starts.append(t); t += 20.0
ch = ml.chapters(SCRIPT, starts)
ck("bolumler: 0:00 ile baslar, >=3, formatli", ch[0].startswith("0:00 ") and len(ch) >= 3 and all(re.match(r"^\d+:\d\d ", c) for c in ch), ch[:2])

# --- kartlar: her sahne turu ve cumle icin hatasiz cizilir
ok_cards, err = True, ""
try:
    for sc in SCRIPT["scenes"]:
        for j in range(len(sc["sentences"])):
            im = ml.render_card(SCRIPT, sc, j, 0.5); assert im.size == (ml.W, ml.H)
except Exception as e:
    ok_cards, err = False, repr(e)
ck("tum kartlar (57 cumle) hatasiz cizilir, 1920x1080", ok_cards, err)
# --- skor tablosu: kapanis cumlesi footer'a (alt 90 px) binmemeli (10-14 gercek render'da goruldu)
sb = next(s for s in SCRIPT["scenes"] if s["kind"] == "scoreboard")
blank = copy.deepcopy(sb); blank["sentences"] = [dict(x, en="x") for x in blank["sentences"]]
band = (0, ml.H - 88, ml.W, ml.H - 12)
overlap = []
for j in range(len(sb["sentences"])):
    a = ml.render_card(SCRIPT, sb, j, 0.5).crop(band).tobytes()
    b = ml.render_card(SCRIPT, blank, j, 0.5).crop(band).tobytes()
    if a != b: overlap.append(j)
ck("skor tablosu: gövde metni footer bandina binmez (tum cumleler)", not overlap, overlap)
src = open(os.path.join("_studio", "make_longform.py"), encoding="utf-8").read()
ck("modulde GOMULU anahtar yok (Voice Mesh anahtari ortam degiskeninden)", not [x for x in re.findall(r"[A-Za-z0-9_\-]{36,}", re.sub(r"https?://\S+", "", src)) if re.search(r"[A-Za-z]", x) and re.search(r"[0-9]", x)] and "AURA_VOICE_KEY" in src)

# --- GERCEK HTTP akisi (kucuk cozunurluk, sahte ses, sahte yayin betigi)
ml.W, ml.H = 960, 540
ml.MIN_EST_SEC = 0   # kucultulmus test senaryosu 3 dk'dan kisa
ml.voice_mesh_tts = lambda url, key, **k: ml.fake_tts
s_ = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s_); s_.loader.exec_module(m)
tmp = tempfile.mkdtemp()
m.LONGFORM_DIR = os.path.join(tmp, "longform"); os.makedirs(m.LONGFORM_DIR)
m.OUTPUT_DIR = os.path.join(tmp, "output"); os.makedirs(m.OUTPUT_DIR)
m.VIDEO_WORK_DIR = os.path.join(tmp, "work")
mini = copy.deepcopy(SCRIPT)
for sc in mini["scenes"]:
    if sc["kind"] == "evidence":
        sc["sentences"] = sc["sentences"][:3] + sc["sentences"][-2:]   # 3 kanit + why + change
mini["scenes"] = [sc for sc in mini["scenes"] if not (sc["kind"] in ("claim", "evidence", "verdict") and sc["n"] == 4)]
for sc in mini["scenes"]:
    if sc["kind"] in ("claim", "evidence", "verdict"): sc["of"] = 3
sb = next(sc for sc in mini["scenes"] if sc["kind"] == "scoreboard")
sb["rows"], sb["rows_verdicts"] = sb["rows"][:3], sb["rows_verdicts"][:3]
sb["sentences"] = [x for x in sb["sentences"] if "Claim four" not in x["en"]]
json.dump(mini, open(os.path.join(m.LONGFORM_DIR, "mini.json"), "w", encoding="utf-8"), ensure_ascii=False)
ck("kucultulmus senaryo kurallardan gecer", blockers(mini) == [], blockers(mini))
fake_pub = os.path.join(tmp, "fake_publish.py")
open(fake_pub, "w").write("import sys\nprint('Link: https://youtu.be/FAKE12345')\n")
m.PUBLISH_SCRIPT = fake_pub
import insights
insights.channel_stats = lambda force=False: {"videos": [{"title": "Some Other Video"}]}
m._verify_tr = lambda vid, srt: True
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
def http(method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, None
c, j = http("GET", "/api/longform/list")
ck("HTTP GET /api/longform/list: 200, senaryo listelenir, render yok", c == 200 and j["ok"] and j["scripts"][0]["name"] == "mini.json" and not j["scripts"][0]["rendered"] and j["scripts"][0]["blockers"] == [], (c, str(j)[:160]))
c, j = http("POST", "/api/longform/publish", {"name": "mini.json", "privacy": "unlisted", "confirm": True})
ck("render olmadan yayin reddedilir", c == 200 and j["ok"] is False and "render" in j["error"].lower(), j)
c, j = http("POST", "/api/longform/render", {"name": "../../etc/passwd.json"})
ck("yol gecisi (path traversal) reddedilir", c == 200 and j["ok"] is False, j)
c, j = http("POST", "/api/longform/render", {"name": "mini.json"})
ck("HTTP POST /api/longform/render: baslar", c == 200 and j["ok"] and j["started"] == "mini.json", (c, j))
c2, j2 = http("POST", "/api/longform/render", {"name": "mini.json"})
ck("calisirken ikinci render reddedilir", j2 and j2["ok"] is False, j2)
for _ in range(240):
    time.sleep(1); c, j = http("GET", "/api/longform/list")
    if j["job"]["state"] != "running": break
job = j["job"]
ck("render bitti (hata yok)", job["state"] == "done", job)
f = m._lf_files("mini.json")
ck("mp4 + TR/EN srt + aciklama uretildi", all(os.path.exists(f[k]) for k in ("mp4", "tr_srt", "en_srt", "description")))
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f["mp4"]], capture_output=True, text=True).stdout)
tr = open(f["tr_srt"], encoding="utf-8").read()
cues = re.findall(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", tr)
end = lambda c: int(c[4]) * 3600 + int(c[5]) * 60 + int(c[6]) + int(c[7]) / 1000
n_sent = sum(len(s["sentences"]) for s in mini["scenes"])
ck("TR altyazi: cumle sayisindan az degil, son cue video suresinden sonra bitmiyor", len(cues) >= n_sent and end(cues[-1]) <= dur + 0.2, (len(cues), n_sent, end(cues[-1]), dur))
ck("TR altyazida Turkce metin var, EN altyazida yok", "yapay" in tr.lower() and not re.search(r"[çğıöşüÇĞİÖŞÜ]", open(f["en_srt"], encoding="utf-8").read()))
dsc = open(f["description"], encoding="utf-8").read()
ck("aciklama: CHAPTERS + SOURCES + AI aciklamasi", "CHAPTERS" in dsc and "0:00 Intro" in dsc and "SOURCES" in dsc and "I'm Aura, an AI" in dsc)
c, j = http("POST", "/api/longform/publish", {"name": "mini.json", "privacy": "unlisted", "confirm": False})
ck("confirm:true olmadan yayin reddedilir", j["ok"] is False and "confirm" in j["error"])
c, j = http("POST", "/api/longform/publish", {"name": "mini.json", "privacy": "friends", "confirm": True})
ck("gecersiz gorunurluk reddedilir", j["ok"] is False)
c, j = http("POST", "/api/longform/publish", {"name": "mini.json", "privacy": "unlisted", "confirm": True})
ck("onayli yayin: link + TR CC dogrulama + sidecar", c == 200 and j["ok"] and j["link"].endswith("FAKE12345") and j["tr_cc"] and os.path.exists(f["published"]), (c, j))
c, j = http("POST", "/api/longform/publish", {"name": "mini.json", "privacy": "unlisted", "confirm": True})
ck("ikinci yayin (cift yayin) engellenir", j["ok"] is False and "zaten" in j["error"], j)
os.remove(f["published"])
insights.channel_stats = lambda force=False: {"videos": [{"title": mini["title"]}]}
c, j = http("POST", "/api/longform/publish", {"name": "mini.json", "privacy": "unlisted", "confirm": True})
ck("kanalda ayni baslik varsa yayin engellenir", j["ok"] is False and "zaten var" in j["error"], j)
srv.shutdown()
print(json.dumps({"total": len(res), "bad": [(n, d) for n, o, d in res if not o]}, ensure_ascii=False))
