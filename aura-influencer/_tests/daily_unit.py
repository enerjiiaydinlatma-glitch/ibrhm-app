"""'Uretim' sekmesi: /api/daily GERCEK HTTP + sayfa JS'inde ters egik cizgi yok + sekme baglantilari."""
import importlib.util as u, json, os, sys, threading, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
import growth
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:200]))
drafts = [{"id": "a1", "title": "Inside Test: 2 Stops", "status": "taslak", "created": "2026-11-27 10:00"},
          {"id": "b2", "title": "Yayinda Olan", "status": "yayinlandi", "video": "aura_yayindaolan.mp4", "link": "https://youtu.be/x", "created": "2026-11-26 10:00"}]
growth.drafts_list = lambda: drafts
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
def get(path):
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=20); return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
c, b = get("/api/daily"); j = json.loads(b or "null")
ck("HTTP GET /api/daily: 200 + ok", c == 200 and j and j.get("ok"), (c, b[:100]))
ck("en yeni taslak ustte, slug dogru", j and j["items"][0]["title"] == "Yayinda Olan" and j["items"][1]["video"] == "aura_insidetest2stops.mp4", j and j["items"])
ck("mutlak cikti klasoru doner", j and os.path.isabs(j["output_dir"]), j and j.get("output_dir"))
c, page = get("/")
ck("sayfa: Uretim sekmesi + view + showTab baglantisi", c == 200 and 'id="btn-tab-daily"' in page and 'id="view-daily"' in page and "['today','daily'," in page)
src = open("aura_studio.py", encoding="utf-8").read()
sa, sz = src.index("// ================= URETIM sekmesi"), src.index("async function gmLoad(){")
ck("kaynakta Uretim JS blogunda ters egik cizgi yok", "\\" not in src[sa:sz])
bad = [n for n, ok, d in res if not ok]
for n, ok, d in res:
    print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
sys.exit(1 if bad else 0)
