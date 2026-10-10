"""Ogrenen sistem (learner.py) birim testi: ag/AI cagrisi YOK, tum dosyalar gecici klasore yonlendirilir."""
import json, os, random, sys, tempfile
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
import learner
tmp = tempfile.mkdtemp()
for n in ("DATA_FILE", "LEARNED_FILE", "HISTORY_FILE", "SCRIPT_LOG", "CTR_FILE", "SNAP_FILE", "RUN_MARK"):
    setattr(learner, n, os.path.join(tmp, os.path.basename(getattr(learner, n))))
learner.REPORT_DIR = os.path.join(tmp, "reports")
learner.PERM, learner.BOOT = 800, 200
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:200]))

# --- ozellikler
sf = learner.script_features("OpenAI fired three safety researchers. They wrote a letter. Follow - I cover one real AI story like this every day. Should OpenAI listen to the researchers it fired?")
ck("script_features: kanca/varlik/dongu/follow", sf["hook_words"] == 5 and sf["hook_has_entity"] and sf["has_loop"] and sf["has_follow_cta"] and sf["ends_with_question"], sf)
ck("follow son cumlede ise has_follow_cta False", not learner.script_features("A thing happened. Follow - I cover one real AI story every day.")["has_follow_cta"])
ck("title_features", learner.title_features("OpenAI Tests Ads")["title_has_entity"] and not learner.title_features("Stop It")["title_has_entity"])

# --- 48 saat izlenmesi
import calendar, time
pub = calendar.timegm(time.strptime("2026-10-01 10:00", "%Y-%m-%d %H:%M"))
snaps = [{"ts": pub + 3600, "videos": {"v": [3, 0, 0]}}, {"ts": pub + 49 * 3600, "videos": {"v": [50, 0, 0]}}, {"ts": pub + 80 * 3600, "videos": {"v": [90, 0, 0]}}]
ck("views_at: yayindan >=48s sonraki ilk kayit", learner.views_at("v", pub, 48, snaps) == 50)
ck("views_at: kayit cok gec basladiysa None", learner.views_at("v", pub, 48, [{"ts": pub + 200 * 3600, "videos": {"v": [9, 0, 0]}}]) is None)
ck("views_at: olgunlasmamis None", learner.views_at("v", pub, 48, snaps[:1]) is None)

# --- CTR CSV (TR + EN, virgullu ondalik, Toplam satiri)
tr_csv = '﻿İçerik,Video başlığı,Gösterimler,Gösterim tıklama oranı (%)\nToplam,,1000,"4,5"\nabc123,Test Video,"1.200","6,25"\n'
r = learner.ctr_import_csv(tr_csv)
st = json.load(open(learner.CTR_FILE))
ck("CTR TR basliklari + virgullu ondalik + Toplam atlanir", r["ok"] and r["imported"] == 1 and st["abc123"]["ctr"] == 6.25 and st["abc123"]["impressions"] == 1200.0, (r, st))
r2 = learner.ctr_import_csv("Content,Video title,Impressions,Impressions click-through rate (%)\nxyz789,Other,500,3.1\n")
ck("CTR EN basliklari", r2["ok"] and json.load(open(learner.CTR_FILE))["xyz789"]["ctr"] == 3.1, r2)
ck("CTR bilinmeyen basliklar acik hata", not learner.ctr_import_csv("a,b\n1,2\n")["ok"])

# --- analiz: gurultuda KURAL YOK, guclu gercek etkide VAR
def mk(n, rng, effect):
    rows = []
    for i in range(n):
        ent = rng.random() < 0.5
        v = max(1, int(rng.lognormvariate(3.0, 0.8) * (5 if (effect and ent) else 1)))
        rows.append({"id": "%03d" % i, "published": "2026-09-%02d 10:00" % (1 + i % 28), "format": rng.choice(["agenda", "template", "other"]),
                     "hook_is_question": rng.random() < .4, "hook_has_number": rng.random() < .3, "hook_has_entity": ent, "has_loop": rng.random() < .5,
                     "has_follow_cta": rng.random() < .2, "ends_with_question": rng.random() < .8, "title_has_number": rng.random() < .2,
                     "title_has_entity": rng.random() < .4, "title_is_question": rng.random() < .1, "hook_words": rng.randint(4, 12),
                     "n_words": rng.randint(40, 70), "duration_s": rng.uniform(15, 28), "title_len": rng.randint(15, 35),
                     "outcome_views": v, "retention": rng.uniform(20, 90), "early_ret": rng.uniform(40, 95), "subs": 0})
    return rows
rng = random.Random(3)
fp = sum(1 for k in range(6) for f in learner.analyze(mk(40, rng, False)) if f["verdict"] in ("pozitif", "negatif"))
ck("saf gurultu (6 veri seti): yanlis kesif <= 1", fp <= 1, fp)
f = learner.analyze(mk(120, random.Random(4), True))
ck("5x gercek etki (n=120) bulunur", any(x["feature"] == "hook_has_entity" and x["metric"] == "outcome_views" and x["verdict"] == "pozitif" for x in f))
small = learner.analyze(mk(8, random.Random(5), True))
ck("n<5 gruplarda 'yetersiz', kural yok", all(x["verdict"] in ("yetersiz", "belirsiz") for x in small))

# --- kural guncelleme: whitelist, gecmis, sert kurallar
try:
    learner._set_knob({}, "max_title_len", 10, "x"); ck("SOFT_KNOBS disi ayar reddedilir", False)
except ValueError:
    ck("SOFT_KNOBS disi ayar reddedilir", True)
rows = mk(120, random.Random(4), True)
fd = learner.analyze(rows)
learned, changed = learner.update_rules(rows, fd)
ck("etki varken hook_hints guncellendi ve gecmise yazildi", "hook_hints" in changed and any(h["feature"] == "hook_has_entity" for h in learned["hook_hints"]) and json.load(open(learner.HISTORY_FILE)), changed)
ck("learned.json sert kurallari listeler, yalniz soft ayarlar degisir", learned["hard_rules_untouched"] == list(learner.HARD_RULES) and set(changed) <= set(learner.SOFT_KNOBS))
ctx = learner.prompt_context()
ck("prompt_context: yumusak ipucu + 'asla ustune cikmaz' uyarisi", "NEVER override" in ctx and "first sentence" in ctx, ctx[:160])
learner._js(learner.LEARNED_FILE, {})
ck("kanit yoksa prompt_context bos", learner.prompt_context() == "")
learner._js(learner.LEARNED_FILE, {"duration_sec_range": [18, 26]})
sc = learner.soft_checks("x", 20.0) + learner.soft_checks("x", 40.0)
ck("soft_checks asla False (bloklamaz)", all(o in (True, None) for o, _, _ in sc), sc)

# --- uctan uca (ag yok): collect + run_once
stats = {"videos": [{"id": "v%02d" % i, "title": "OpenAI Thing %d" % i, "published": "2026-09-%02d 10:00" % (1 + i % 28), "views": 20 + i,
                     "likes": 1, "comments": 0, "privacy": "public"} for i in range(12)] + [{"id": "priv", "title": "Hidden", "published": "2026-09-01 10:00", "views": 9, "likes": 0, "comments": 0, "privacy": "unlisted"}]}
an = [{"video_id": "v00", "avg_pct": 50.0, "avg_sec": 10.0, "subs": 1}]
learner.log_script("v00", "OpenAI Thing 0", "OpenAI did a thing. It matters. Follow - I cover one real AI story like this every day. Should OpenAI care?")
rows = learner.collect(stats, an, {}, fetch_early=False)
r0 = next(x for x in rows if x["id"] == "v00")
ck("collect: listelenmemis video disarida, sure = avg_sec/avg_pct", len(rows) == 12 and r0["duration_s"] == 20.0 and r0["has_follow_cta"])
import insights
insights.channel_stats = lambda force=False: stats
insights.analytics_report = lambda days=28: {"rows": an}
insights.tt_latest = lambda: {}
out = learner.run_once(force_fetch=False)
ck("kanit kalmayinca bayat sure ayari temizlenir (gecmise yazilir)", out["changed"] == ["duration_sec_range"] and json.load(open(learner.LEARNED_FILE))["duration_sec_range"] is None, out["changed"])
os.remove(learner.RUN_MARK)
out = learner.run_once(force_fetch=False)
ck("run_once: rapor yazar, kanit yoksa HICBIR SEY der, hicbir yayin cagrisi yok", out["ok"] and "HICBIR SEY" in out["text"] and os.path.exists(os.path.join(learner.REPORT_DIR, out["report"])), out["text"][300:900] + str(out["changed"]))
ck("run_daily: 20 saat icinde tekrar calismaz", learner.run_daily().get("skipped"))
print(json.dumps({"total": len(res), "bad": [(n, d) for n, o, d in res if not o]}, ensure_ascii=False))
