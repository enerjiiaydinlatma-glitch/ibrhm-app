"""'Bugun' ana yuzu sunucu tarafi birim testi (ag/AI cagrisi yok; veri kaynaklari sahte)."""
import importlib.util as u, json, os, sys, time
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
import insights, growth
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:200]))
now = time.time()
def pub(h): return time.strftime("%Y-%m-%d %H:%M", time.gmtime(now - h * 3600))
vids = [{"id": "a", "title": "Live Video One", "published": pub(100), "views": 50, "likes": 2, "comments": 1, "privacy": "public"},
        {"id": "b", "title": "Older Video", "published": pub(300), "views": 10, "likes": 0, "comments": 0, "privacy": "public"},
        {"id": "c", "title": "Hidden", "published": pub(10), "views": 5, "likes": 0, "comments": 0, "privacy": "unlisted"}]
stats = {"videos": vids, "subscribers": 2, "total_views": 65, "video_count": 3}
insights.channel_stats = lambda force=False: stats
insights.trend = lambda st: {"series": [{"at": "2026-10-01 10:00", "subs": 2, "total_views": 40}, {"at": "2026-10-10 10:00", "subs": 2, "total_views": 65}]}
insights.analytics_status = lambda: {"authorized": False}
insights.tt_latest = lambda: {"a": {"video_id": "a", "views": 120, "likes": 3, "comments": 0, "shares": 0, "date": "2026-10-10"}}
insights._jload = lambda path, default: [{"ts": now - 8 * 86400, "total_views": 40, "videos": {}}]
rows = [{"day": 10, "title": "Live Video One", "youtube": True, "youtube_id": "a", "tiktok": False, "tr_cc": True},
        {"day": 9, "title": "Old", "youtube": True, "youtube_id": "z", "tiktok": False, "tr_cc": False},
        {"day": 2, "title": "Ancient", "youtube": True, "tiktok": False, "tr_cc": False},
        {"day": 8, "title": "Skipped", "youtube": True, "tiktok": False, "tiktok_skip": True, "tr_cc": True}]
m._load_day_status = lambda: rows
growth.drafts_list = lambda: [{"id": "d1", "title": "Live Video One", "status": "render edildi"}, {"id": "d2", "title": "Pending Render", "status": "render edildi"}]
d = m._today_state()
txt = " | ".join(t["text"] for t in d["todo"])
ck("ok + 3 videodan yalniz 2'si herkese acik sayilir (listelenmemis disarida)", d["ok"] and d["n_videos"] == 2 and len(d["bars"]) == 2, d.get("errors"))
ck("son video 36 saatten eskiyse 'yeni video' uyarisi", any(t["go"] == "trends" and t["level"] == "warn" for t in d["todo"]), txt)
ck("render edilmis ama ZATEN YAYINDA olan taslak 'yayin bekliyor' diye onerilmez (Gun 40 korumasi)", "Live Video One. YouTube" not in txt and "Pending Render" in txt, txt)
ck("TikTok eksigi yalniz son gunlerden ve atlanmayanlardan", "Gun 10" in txt and "Gun 2 " not in txt and "Skipped" not in txt, txt)
ck("Turkce CC eksigi yalniz son gunlerden", "Gun 9" in txt and "Ancient" not in txt, txt)
ck("son 7 gun artisi gercek zaman damgasindan", d["week_views"] == 25, d.get("week_views"))
ck("bar verisi: TikTok izlenmesi ve etkilesim orani", d["bars"][-1]["tt_views"] == 120 and d["bars"][-1]["eng"] == 6.0, d["bars"][-1])
ck("tum bolumler hatasiz", not d["errors"], d["errors"])
tr = m._trends(cached_only=True)
ck("trendler: onbellek yoksa AG CAGRISI YAPMAZ, bos doner", tr["ok"] and tr["items"] == [], tr)
print(json.dumps({"total": len(res), "bad": [(n, dd) for n, o, dd in res if not o]}, ensure_ascii=False))
