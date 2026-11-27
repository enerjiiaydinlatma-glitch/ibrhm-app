"""Olcum panosu: /api/measure (GERCEK HTTP), ~24/48 sa sayac okuma, ort. izlenme % birlestirme, seri gruplari, Analytics yoksa acik uyari."""
import importlib.util as u, json, os, sys, threading, time, calendar, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
import insights, growth
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
now = time.time()
def pub(h): return time.strftime("%Y-%m-%d %H:%M", time.gmtime(now - h * 3600))
vids = [{"id": "a", "title": "Inside Fresh: 2 Stops", "published": pub(22), "views": 100, "likes": 1, "comments": 0, "privacy": "public"},
        {"id": "b", "title": "Inside Old: 2 Stops", "published": pub(80), "views": 240, "likes": 2, "comments": 1, "privacy": "public"},
        {"id": "c", "title": "Robot Store Shift: 4 of 6 Passed", "published": pub(120), "views": 80, "likes": 0, "comments": 0, "privacy": "public"},
        {"id": "d", "title": "Hidden One", "published": pub(10), "views": 5, "likes": 0, "comments": 0, "privacy": "unlisted"}]
stats = {"videos": vids, "subscribers": 2, "total_views": 425, "video_count": 4}
insights.channel_stats = lambda force=False: stats
t_b = calendar.timegm(time.strptime(vids[1]["published"], "%Y-%m-%d %H:%M"))
snaps = [{"ts": t_b + 25 * 3600, "at": "x", "subs": 2, "total_views": 200, "videos": {"b": [150, 1, 0], "a": [0, 0, 0]}},
         {"ts": t_b + 49 * 3600, "at": "y", "subs": 2, "total_views": 300, "videos": {"b": [220, 2, 1]}}]
insights._jload = lambda path, default: snaps if path == insights.SNAP_FILE else default
insights.tt_latest = lambda: {"b": {"views": 130, "likes": 3, "comments": 0, "shares": 1}}
insights.trend = lambda st: {"series": []}
insights.analytics_report = lambda days=28: {"rows": [{"video_id": "b", "avg_pct": 52.3, "avg_sec": 14.4, "subs": 0}]}
d = m._measure_state()
rows = {r["id"]: r for r in d["rows"]}
ck("yalniz herkese acik videolar (listelenmemis disarida)", set(rows) == {"a", "b", "c"}, list(rows))
ck("~24 sa izlenme: yayindan 24 sa sonraki en yakin sayac kaydi", rows["b"]["v24"] == 150, rows["b"]["v24"])
ck("~48 sa izlenme", rows["b"]["v48"] == 220, rows["b"]["v48"])
ck("henuz 24 saat dolmamis videoda ~24 sa bos", rows["a"]["v24"] is None)
ck("kaydi olmayan video bos doner (uydurma yok)", rows["c"]["v24"] is None and rows["c"]["v48"] is None)
ck("ort. izlenme % Analytics'ten birlesir", rows["b"]["avg_pct"] == 52.3 and rows["a"]["avg_pct"] is None, rows["b"])
ck("TikTok sutunu eslesen videoda dolu", rows["b"]["tt_views"] == 130 and rows["a"]["tt_views"] is None)
ck("24 saat olcumu zamani bayragi (20-36 sa)", rows["a"]["due24"] and not rows["b"]["due24"], (rows["a"]["age_h"], rows["b"]["age_h"]))
ck("seri: Inside=Tour, Robot Store=Gundem", rows["b"]["series"] == "Tour" and rows["c"]["series"] in ("Gundem", "Diger"), (rows["b"]["series"], rows["c"]["series"]))
ck("grup medyani", any(g["name"] == "Tour" and g["n"] == 2 for g in d["groups"]), d["groups"])
insights.analytics_report = lambda days=28: (_ for _ in ()).throw(RuntimeError("Analytics yetkisi yok."))
d2 = m._measure_state()
ck("Analytics yoksa acik uyari + panel calisir", d2["ok"] and not d2["analytics"] and d2["errors"] and all(r["avg_pct"] is None for r in d2["rows"]), d2["errors"])
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/measure", timeout=20); j = json.loads(r.read().decode())
ck("HTTP GET /api/measure: 200 + ok", r.status == 200 and j.get("ok") and len(j["rows"]) == 3, str(j)[:100])
page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=20).read().decode()
ck("sayfa: Olcum sekmesi + view + showTab", 'id="btn-tab-measure"' in page and 'id="view-measure"' in page and "'measure'" in page)
src = open("aura_studio.py", encoding="utf-8").read()
a, z = src.index("// ================= OLCUM panosu"), src.index("async function gmLoad(){")
ck("kaynakta Olcum JS blogunda ters egik cizgi yok", "\\" not in src[a:z])
bad = [n for n, ok, d in res if not ok]
for n, ok, d in res: print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
sys.exit(1 if bad else 0)
