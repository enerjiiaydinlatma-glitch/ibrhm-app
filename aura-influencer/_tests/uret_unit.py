"""uret.py (terminalden uretim): onay yazmadan render/yayin YOK; GERCEK HTTP ile panelin API'sini kullanir."""
import importlib.util as u, json, os, sys, threading
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
s2 = u.spec_from_file_location("uret", "uret.py"); uret = u.module_from_spec(s2); s2.loader.exec_module(uret)
import growth
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
store = []
growth.drafts_list = lambda: list(store)
growth.draft_add = lambda d: (store.append({"id": "t%d" % (len(store) + 1), "status": "taslak", "created": "2026-11-28 10:00", **d}) or store[-1])
growth.draft_get = lambda i: next((x for x in store if x["id"] == i), None)
m._safe_channel_titles = lambda: []
m._growth_state = lambda: {"ok": True, "drafts": store[::-1]}
calls = {"render": 0, "publish": 0, "confirm": None}
def fake_render(did):
    calls["render"] += 1
    d = growth.draft_get(did); d["status"] = "render edildi"; d["video"] = "aura_test.mp4"
    open(os.path.join(m.OUTPUT_DIR, "aura_test.mp4"), "wb").write(b"x")
    return {"ok": True, "video": "aura_test.mp4", "warning": ""}
def fake_publish(did, day=None):
    calls["publish"] += 1
    growth.draft_get(did)["status"] = "yayinlandi"
    return {"ok": True, "link": "https://youtu.be/TEST"}
m._growth_render_draft = fake_render
m._growth_publish_draft = fake_publish
os.makedirs(m.OUTPUT_DIR, exist_ok=True)
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
uret.BASE = f"http://127.0.0.1:{port}"
clip = []
uret.copy_clip = lambda t: clip.append(t) or True
def run(argv, answers):
    log, it = [], iter(answers)
    code = uret.main(argv, inp=lambda p: (log.append("? " + p) or next(it, "")), opener=lambda p: log.append("OPEN " + p), out=lambda *a: log.append(" ".join(str(x) for x in a)))
    return code, "\n".join(log)
store.append({"id": "t0", "title": "Inside Test: Tomb or Temple?", "status": "taslak", "created": "x", "en_script": "Tomb or temple? I'm Aura, an AI, in my 3D rebuild, not real footage. Comment A or B.",
              "tr_script": "Mezar mi, tapinak mi? Ben Aura, yapay zekayim; 3B yapimimdayim, gercek goruntu degil. A ya da B yaz.", "description": "Desc", "tiktok_description": "TT caption #AuraAI", "rationale": "kaynak: test", "preflight": {"score": 18, "of": 18, "est_seconds": 25}})
c, log = run([], [])
ck("argumansiz: bekleyen isleri listeler, hicbir sey yapmaz", c == 0 and "Inside Test" in log and calls["render"] == 0, log)
c, log = run(["yokboyle"], [])
ck("eslesme yoksa net mesaj", c == 1 and "yok" in log)
c, log = run(["inside test"], ["hayir"])
ck("EVET yazilmazsa render/yayin YOK", c == 0 and calls["render"] == 0 and calls["publish"] == 0 and "Onay verilmedi" in log, log[-200:])
c, log = run(["inside test"], ["EVET", ""])
ck("onay + yayinlama onayi bos: render olur, YAYIN OLMAZ", c == 0 and calls["render"] == 1 and calls["publish"] == 0 and "Yayinlanmadi" in log, log[-250:])
ck("video oynaticiya acilir (opener)", "OPEN" in log and "aura_test.mp4" in log, log[-400:])
c, log = run(["inside test"], ["Evet", "yayınla"])
ck("YAYINLA yazilinca yayinlanir; link + TikTok paketi + panoya aciklama", c == 0 and calls["publish"] == 1 and "https://youtu.be/TEST" in log and clip and clip[-1] == "TT caption #AuraAI", (calls, clip))
ck("sabit yorum onerilir", "Comment A or B." in log)
c, log = run(["inside test"], [])
ck("yayinlanmis taslak bekleyen listesinde degil", c == 1, log)
store.append({"id": "t9", "title": "Bad Draft Promise", "status": "taslak", "created": "x", "en_script": "I will show you every real number.", "tr_script": "Bütün rakamlari gostereyim.", "description": "x", "rationale": ""})
n = calls["render"]
c, log = run(["bad draft"], ["EVET", "hayir"])
ck("uyarili taslak: EVET yetmez, DEVAM gerekir; vaat ve ibare uyarisi gorunur", c == 0 and calls["render"] == n and "vaadi" in log and "not real footage" in log, log[-300:])
uret.BASE = "http://127.0.0.1:1"
c, log = run(["x"], [])
ck("panel kapaliysa acik hata (donus kodu 2)", c == 2 and "Panele ulasilamadi" in log, log)
ck("buyuk/kucuk harf ve Turkce harf farki onaya engel degil (Evet, yayınla), yanlis kelime hala reddedilir", uret.norm("YAYINLA") == uret.norm("yayınla") == "yayinla" and uret.norm("Evet") == "evet" and uret.norm("evt") != "evet")
bad = [n_ for n_, ok, d in res if not ok]
for n_, ok, d in res: print(("OK  " if ok else "FAIL"), n_, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
try: os.remove(os.path.join(m.OUTPUT_DIR, "aura_test.mp4"))
except Exception: pass
sys.exit(1 if bad else 0)
