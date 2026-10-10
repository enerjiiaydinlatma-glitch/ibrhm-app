"""Ogrenen sistem (2026-10-10): veriyi toplar, istatistiksel olarak ANALIZ eder, kanitlanabilen
YUMUSAK ayarlari gunceller. Hicbir seyi yayinlamaz, hicbir YouTube/TikTok yazma islemi yapmaz.

Tasarim ilkeleri (bilincli):
- Orneklem kucuk (onlarca video). Bu yuzden "sasirtici oruntu" aramak gurultu kovalamaktir: her ozellik icin
  bootstrap %99 guven araligi + her iki grupta en az MIN_N video sart. Cogu hafta SONUC CIKMAYACAK - bu normaldir,
  sistem o zaman hicbir seyi degistirmez ve nedenini rapora yazar.
- HARD_RULES asla otomatik degismez. Sadece SOFT_KNOBS whitelist'indeki ayarlar guncellenir; her degisiklik
  kanitiyla birlikte learned_history.json'a yazilir (geri alinabilir, denetlenebilir).
- CTR/gosterim YouTube Analytics API'de YOK (platform kisiti). Elle: YouTube Studio "Verileri indir" CSV'si
  ctr_import_csv() ile alinir ve analize girer.
"""
import csv
import io
import json
import math
import os
import random
import re
import statistics as S
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DATA_FILE = os.path.join(HERE, "learn_data.json")
LEARNED_FILE = os.path.join(HERE, "learned.json")
HISTORY_FILE = os.path.join(HERE, "learned_history.json")
SCRIPT_LOG = os.path.join(HERE, "script_log.json")
CTR_FILE = os.path.join(HERE, "ctr_manual.json")
SNAP_FILE = os.path.join(HERE, "snapshots.json")
REPORT_DIR = os.path.join(HERE, "reports")
RUN_MARK = os.path.join(HERE, "learn_last_run.txt")

MIN_N = 5            # her karsilastirma grubunda en az bu kadar video
ALPHA_CI = 0.99      # sadece GOSTERIM icin guven araligi
BOOT = 1000
PERM = 2000          # permutasyon testi (p-degeri)
FDR_Q = 0.10         # Benjamini-Hochberg: ~50 test ayni anda yapiliyor, yanlis kesif orani <= %10

# Otomatik DEGISMEYEN kurallar (operatorun kalici kararlari + proje guvenlik kurallari).
HARD_RULES = (
    "Her sey Ingilizce (ses/altyazi/baslik/aciklama/etiket); tek istisna YouTube'da ayri Turkce CC parcasi",
    "Haber/rakam/iddia uydurulmaz; gundem taslagi yayindan once bagimsiz dogrulanir",
    "Aura acikca AI oldugunu soyler; kendi yetenegi hakkinda iddia yok; cinsel icerik yok",
    "Yayin sadece operator onayiyla; sahte metrik/aciliyet/sahte etkilesim yok",
    "growth.preflight() hard kontrolleri (kanca/uzunluk/CC guvenligi) bu modulle gevsetilmez",
)
# Sadece bunlar otomatik guncellenebilir (hepsi YUMUSAK ipucu; preflight'ta bloklamaz, prompt'a ipucu olarak girer).
SOFT_KNOBS = ("duration_sec_range", "hook_hints", "topic_hints", "title_hints")

ENTITY_RE = re.compile(r"\b(openai|anthropic|google|gemini|deepmind|meta|nvidia|microsoft|xai|mistral|apple|amazon|"
                       r"claude|chatgpt|gpt-?\d*|ftc|eu|white house)\b", re.I)


def _jl(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def _js(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ scriptlerin kaydi
def log_script(video_id, title, en_script):
    """Yayin aninda cagrilir: kanca/dongu ozelliklerini sonradan cikarabilmek icin script'i saklar."""
    if not video_id or not en_script:
        return
    d = _jl(SCRIPT_LOG, {})
    d[video_id] = {"title": title, "en_script": en_script, "at": time.strftime("%Y-%m-%d %H:%M")}
    _js(SCRIPT_LOG, d)


# ------------------------------------------------------------------ ozellik cikarma
def _g():
    import growth
    return growth


def script_features(en):
    g = _g()
    sents = g._sentences(en or "")
    if not sents:
        return {}
    hook = sents[0]
    hw = g._words(hook)
    first_w = {w.lower() for w in g._words(sents[0])} - g._LOOP_STOP
    last_w = {w.lower() for w in g._words(sents[-1])} - g._LOOP_STOP
    f = {
        "hook_words": len(hw),
        "hook_is_question": hook.strip().endswith("?"),
        "hook_has_number": bool(re.search(r"\d", hook)),
        "hook_has_entity": bool(ENTITY_RE.search(hook)),
        "n_sentences": len(sents),
        "n_words": len(g._words(en)),
        "has_loop": bool(first_w & last_w),
        "has_follow_cta": any(g.FOLLOW_CTA.search(x) for x in sents[:-1]),
        "ends_with_question": sents[-1].strip().endswith("?"),
    }
    return f


def title_features(title):
    t = title or ""
    return {
        "title_len": len(t),
        "title_has_number": bool(re.search(r"\d", t)),
        "title_has_entity": bool(ENTITY_RE.search(t)),
        "title_is_question": t.strip().endswith("?"),
    }


def _pub_ts(published):
    import calendar
    try:
        return calendar.timegm(time.strptime(published[:16], "%Y-%m-%d %H:%M"))
    except Exception:
        return None


def views_at(video_id, pub_ts, hours, snaps):
    """Yayindan `hours` saat sonraki ILK sayac kaydindaki izlenme (yoksa None: olgunlasmamis ya da kayit baslamadan once)."""
    if pub_ts is None:
        return None
    for s in snaps:
        if s["ts"] >= pub_ts + hours * 3600:
            # kayit yayindan cok sonra basladiysa (>12 sa fark) 48 saat verisi sayilmaz
            if s["ts"] - (pub_ts + hours * 3600) > 12 * 3600:
                return None
            v = s["videos"].get(video_id)
            return v[0] if v else None
    return None


# ------------------------------------------------------------------ CTR (elle CSV)
def _num(x, integer=False):
    x = str(x).strip().replace("%", "").replace(" ", "").replace(" ", "")
    if not x:
        return None
    if integer:  # gosterim sayisi: '.' ve ',' binlik ayraci (TR: 1.200 = 1200)
        x = x.replace(".", "").replace(",", "")
    elif "," in x and "." in x:
        x = x.replace(".", "").replace(",", ".") if x.rfind(",") > x.rfind(".") else x.replace(",", "")
    else:
        x = x.replace(",", ".")
    try:
        return float(x)
    except ValueError:
        return None


def _tl(s):
    """Turkce-duyarli kucuk harf: 'İ'.lower() Python'da 'i' + birlestirici nokta uretir ve eslesmeleri bozar."""
    return str(s).strip().replace("İ", "i").replace("I", "ı").lower()


def ctr_import_csv(text):
    """YouTube Studio > Analytics > Verileri indir > 'Tablo verileri.csv' (TR/EN basliklar). Sutunlar baslik
    alt-dizgisiyle bulunur. GERCEK dosyayla henuz denenmedi: basliklar eslesmezse hata mesaji hangi sutunu
    bulamadigini soyler."""
    rdr = csv.reader(io.StringIO(text.lstrip("﻿")))
    rows = list(rdr)
    if len(rows) < 2:
        return {"ok": False, "error": "CSV bos."}
    hdr = [_tl(h) for h in rows[0]]

    def find(pred):
        for i, h in enumerate(hdr):
            if pred(h):
                return i
        return None
    i_id = find(lambda h: h in ("içerik", "icerik", "content", "video", "ıçerik"))
    i_title = find(lambda h: "başlı" in h or "baslik" in h or "title" in h)
    i_ctr = find(lambda h: "tıklama oranı" in h or "tiklama orani" in h or "click-through" in h or h == "ctr")
    i_imp = find(lambda h: (h.startswith("gösterim") or h.startswith("gosterim") or h.startswith("impressions"))
                 and "oran" not in h and "click" not in h)
    if i_ctr is None or (i_id is None and i_title is None):
        return {"ok": False, "error": f"Sutun bulunamadi (ctr={i_ctr}, id={i_id}, baslik={i_title}). Basliklar: {rows[0][:12]}"}
    store = _jl(CTR_FILE, {})
    n = 0
    for r in rows[1:]:
        if len(r) <= i_ctr:
            continue
        key = (r[i_id].strip() if i_id is not None and i_id < len(r) else "") or ""
        title = r[i_title].strip() if i_title is not None and i_title < len(r) else ""
        ctr = _num(r[i_ctr])
        if ctr is None or not (key or title) or _tl(key) == "toplam" or _tl(title) == "toplam":
            continue
        store[key or ("t:" + title.lower())] = {"ctr": ctr, "title": title,
                                                "impressions": _num(r[i_imp], integer=True) if i_imp is not None and i_imp < len(r) else None,
                                                "at": time.strftime("%Y-%m-%d")}
        n += 1
    _js(CTR_FILE, store)
    return {"ok": True, "imported": n}


def _ctr_for(vid, title, store):
    if vid in store:
        return store[vid]
    return store.get("t:" + (title or "").lower())


# ------------------------------------------------------------------ erken tutma (ilk saniyeler)
def early_retention(video_id, ratio=0.10):
    """YouTube Analytics API: elapsedVideoTimeRatio boyutu + audienceWatchRatio metrigi (video filtresiyle).
    ratio=0.10 -> videonun ilk %10'unda (20 sn'lik videoda ~2. saniye) izleyicilerin ne kadari hala orada.
    CANLI test EDILMEDI (bu ortamda yetki yok); hata olursa None doner, sistem bunsuz da calisir."""
    try:
        from googleapiclient.discovery import build
        import insights
        c = insights.analytics_creds()
        if c is None:
            return None
        ya = build("youtubeAnalytics", "v2", credentials=c)
        end = time.strftime("%Y-%m-%d")
        start = time.strftime("%Y-%m-%d", time.localtime(time.time() - 120 * 86400))
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, metrics="audienceWatchRatio",
                               dimensions="elapsedVideoTimeRatio", filters=f"video=={video_id}").execute()
        pts = {round(float(x[0]), 2): float(x[1]) for x in r.get("rows", [])}
        if not pts:
            return None
        k = min(pts, key=lambda a: abs(a - ratio))
        return round(pts[k] * 100, 1)
    except Exception:
        return None


# ------------------------------------------------------------------ veri toplama
def collect(stats=None, analytics_rows=None, tt=None, fetch_early=True, max_early=8):
    """Her video icin ozellik + sonuc satirlari. Satirlar learn_data.json'a yazilir (video id'ye gore guncellenir)."""
    import insights
    import growth
    if stats is None:
        stats = insights.channel_stats()
    if analytics_rows is None:
        try:
            analytics_rows = insights.analytics_report()["rows"]
        except Exception:
            analytics_rows = []
    if tt is None:
        try:
            tt = insights.tt_latest()
        except Exception:
            tt = {}
    snaps = _jl(SNAP_FILE, [])
    scripts = _jl(SCRIPT_LOG, {})
    ctrs = _jl(CTR_FILE, {})
    an = {r["video_id"]: r for r in analytics_rows}
    tags = growth.tags_load()
    old = {r["id"]: r for r in _jl(DATA_FILE, [])}
    now = time.time()
    out = []
    n_early = 0
    for v in stats["videos"]:
        if v.get("privacy") not in (None, "public"):
            continue  # listelenmemis/ozel videolar dagitima girmedi, analizi bozar
        pts = _pub_ts(v["published"])
        age_days = (now - pts) / 86400 if pts else None
        a = an.get(v["id"], {})
        row = dict(old.get(v["id"], {}))
        row.update({"id": v["id"], "title": v["title"], "published": v["published"], "age_days": round(age_days, 1) if age_days is not None else None,
                    "views": v["views"], "likes": v["likes"], "comments": v["comments"],
                    "format": tags.get(v["id"]) or growth.auto_format(v["title"]),
                    "hour_utc": int(v["published"][11:13]) if len(v["published"]) >= 13 else None,
                    "retention": a.get("avg_pct"), "subs": a.get("subs"),
                    "duration_s": round(a["avg_sec"] / (a["avg_pct"] / 100), 1) if a.get("avg_pct") and a.get("avg_sec") else row.get("duration_s"),
                    "views_48h": views_at(v["id"], pts, 48, snaps) if row.get("views_48h") is None else row["views_48h"]})
        row.update(title_features(v["title"]))
        sc = scripts.get(v["id"])
        if sc:
            row.update(script_features(sc["en_script"]))
        c = _ctr_for(v["id"], v["title"], ctrs)
        if c:
            row["ctr"] = c["ctr"]
        t = tt.get(v["id"])
        if t:
            row["tt_views"] = t.get("views")
        if fetch_early and row.get("early_ret") is None and n_early < max_early and (age_days or 0) >= 3:
            row["early_ret"] = early_retention(v["id"])
            n_early += 1
        # ana sonuc olcusu: 48. saat izlenmesi (yas-normalize); yoksa >=14 gunluk toplam izlenme (olgun); yoksa yok
        if row.get("views_48h") is not None:
            row["outcome_views"] = row["views_48h"]
        elif (age_days or 0) >= 14:
            row["outcome_views"] = v["views"]
        else:
            row["outcome_views"] = None
        out.append(row)
    _js(DATA_FILE, out)
    return out


# ------------------------------------------------------------------ analiz
def _boot_ci(a, b, seed=7):
    """Medyan(a) - medyan(b) icin bootstrap (1-ALPHA_CI) araligi. Deterministik (seed)."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(BOOT):
        sa = [rng.choice(a) for _ in a]
        sb = [rng.choice(b) for _ in b]
        diffs.append(S.median(sa) - S.median(sb))
    diffs.sort()
    lo = diffs[int(BOOT * (1 - ALPHA_CI) / 2)]
    hi = diffs[int(BOOT * (1 - (1 - ALPHA_CI) / 2)) - 1]
    return lo, hi


def _perm_p(a, b, seed=11):
    """Iki yonlu permutasyon testi p-degeri (medyan farki)."""
    rng = random.Random(seed)
    obs = abs(S.median(a) - S.median(b))
    pool = list(a) + list(b)
    na = len(a)
    hit = 0
    for _ in range(PERM):
        rng.shuffle(pool)
        if abs(S.median(pool[:na]) - S.median(pool[na:])) >= obs:
            hit += 1
    return (hit + 1) / (PERM + 1)


def _compare(rows, key, pred, metric):
    got = [r for r in rows if r.get(key) is not None and r.get(metric) is not None]
    a = [r[metric] for r in got if pred(r)]
    b = [r[metric] for r in got if not pred(r)]
    if len(a) < MIN_N or len(b) < MIN_N:
        return {"n_with": len(a), "n_without": len(b), "verdict": "yetersiz"}
    lo, hi = _boot_ci(a, b)
    d = S.median(a) - S.median(b)
    # Yon tutarliligi: etki hem ESKI hem YENI yarida ayni yonde olmali
    ordered = sorted(got, key=lambda r: r.get("published") or r.get("id") or "")
    half = len(ordered) // 2
    signs = []
    for part in (ordered[:half], ordered[half:]):
        pa = [r[metric] for r in part if pred(r)]
        pb = [r[metric] for r in part if not pred(r)]
        if len(pa) < 2 or len(pb) < 2:
            signs.append(0)
        else:
            dd = S.median(pa) - S.median(pb)
            signs.append(1 if dd > 0 else -1 if dd < 0 else 0)
    want = 1 if d > 0 else -1 if d < 0 else 0
    return {"n_with": len(a), "n_without": len(b), "median_with": round(S.median(a), 1), "median_without": round(S.median(b), 1),
            "diff": round(d, 1), "ci": [round(lo, 1), round(hi, 1)], "p": _perm_p(a, b),
            "consistent": want != 0 and signs == [want, want], "verdict": "belirsiz",
            "_dir": "pozitif" if d > 0 else "negatif"}


def _bh_apply(findings):
    """Benjamini-Hochberg: p-degeri olan tum testler uzerinde yanlis kesif oranini FDR_Q'da tutar.
    Verdict ancak (q <= FDR_Q) VE (bootstrap CI sifiri icermiyor) VE (eski/yeni yari ayni yon) ise pozitif/negatif olur."""
    tested = [f for f in findings if "p" in f]
    tested.sort(key=lambda f: f["p"])
    m = len(tested)
    cutoff = 0
    for i, f in enumerate(tested, 1):
        if f["p"] <= FDR_Q * i / m:
            cutoff = i
    for i, f in enumerate(tested, 1):
        f["q_ok"] = i <= cutoff
        ci_ok = f["ci"][0] > 0 or f["ci"][1] < 0
        if f["q_ok"] and ci_ok and f["consistent"]:
            f["verdict"] = f["_dir"]
    for f in findings:
        f.pop("_dir", None)
    return findings


BOOL_FEATURES = ["hook_is_question", "hook_has_number", "hook_has_entity", "has_loop", "has_follow_cta", "ends_with_question",
                 "title_has_number", "title_has_entity", "title_is_question"]
NUM_FEATURES = ["hook_words", "n_words", "duration_s", "title_len"]
METRICS = [("outcome_views", "izlenme (48s / olgun)"), ("retention", "ort. izlenme %"), ("early_ret", "ilk %10 tutma"), ("ctr", "CTR %"),
           ("subs", "kazanilan abone")]


def analyze(rows):
    findings = []
    for f in BOOL_FEATURES:
        for m, mlabel in METRICS:
            r = _compare(rows, f, lambda x, f=f: bool(x.get(f)), m)
            findings.append({"feature": f, "metric": m, "metric_label": mlabel, "kind": "bool", **r})
    for f in NUM_FEATURES:
        vals = [r[f] for r in rows if r.get(f) is not None]
        if len(vals) < 2 * MIN_N:
            for m, mlabel in METRICS:
                findings.append({"feature": f + " (<=medyan)", "metric": m, "metric_label": mlabel, "kind": "num",
                                 "n_with": len(vals), "n_without": 0, "verdict": "yetersiz"})
            continue
        med = S.median(vals)
        for m, mlabel in METRICS:
            r = _compare(rows, f, lambda x, f=f, med=med: x[f] <= med, m)
            findings.append({"feature": f"{f} (<= {round(med, 1)})", "metric": m, "metric_label": mlabel, "kind": "num", **r})
    # format ve konu (varlik) kaldiraci
    for fmt in sorted({r["format"] for r in rows if r.get("format")}):
        r = _compare(rows, "format", lambda x, fmt=fmt: x["format"] == fmt, "outcome_views")
        findings.append({"feature": "format=" + fmt, "metric": "outcome_views", "metric_label": "izlenme (48s / olgun)", "kind": "format", **r})
    return _bh_apply(findings)


def duration_range(rows):
    """Tutmasi en iyi ust ucte (en iyi 1/3) videolarin sure araligi (p25-p75). Yeterli veri yoksa None."""
    pts = [(r["retention"], r["duration_s"]) for r in rows if r.get("retention") is not None and r.get("duration_s")]
    if len(pts) < 9:
        return None
    pts.sort(key=lambda p: -p[0])
    top = sorted(d for _, d in pts[:max(3, len(pts) // 3)])
    q = S.quantiles(top, n=4) if len(top) >= 4 else [top[0], S.median(top), top[-1]]
    return [round(q[0]), round(q[2])]


# ------------------------------------------------------------------ yumusak ayarlari guncelle
def _history(entry):
    h = _jl(HISTORY_FILE, [])
    h.append(entry)
    _js(HISTORY_FILE, h[-300:])


def _set_knob(learned, name, value, evidence):
    if name not in SOFT_KNOBS:
        raise ValueError(f"'{name}' otomatik guncellenemez (SOFT_KNOBS disi).")
    if (learned.get(name) or None) == (value or None):
        learned[name] = value
        return False
    _history({"at": time.strftime("%Y-%m-%d %H:%M"), "knob": name, "old": learned.get(name), "new": value, "evidence": evidence})
    learned[name] = value
    return True


HINT_TEXT = {
    "hook_is_question": ("Open with a direct question", "Open with a statement, not a question"),
    "hook_has_number": ("Put a concrete number in the first sentence", "Avoid numbers in the first sentence"),
    "hook_has_entity": ("Name the company/person in the first sentence", "Do not lead with a company name"),
    "has_loop": ("End by echoing a word from the hook (loop)", "Looping did not help; do not force it"),
    "has_follow_cta": ("Keep the 'Follow - I cover one real AI story...' line", "The Follow line did not help; shorten it"),
    "ends_with_question": ("End on a question", "Do not end on a question"),
}


def update_rules(rows, findings):
    learned = _jl(LEARNED_FILE, {"hook_hints": [], "topic_hints": [], "title_hints": [], "duration_sec_range": None})
    changed = []
    hints = []
    for f in findings:
        if f["metric"] not in ("outcome_views", "early_ret", "ctr") or f["verdict"] not in ("pozitif", "negatif"):
            continue
        key = f["feature"]
        if key in HINT_TEXT:
            pos, neg = HINT_TEXT[key]
            hints.append({"text": pos if f["verdict"] == "pozitif" else neg, "feature": key, "metric": f["metric"],
                          "diff": f["diff"], "ci": f["ci"], "n": [f["n_with"], f["n_without"]]})
    if _set_knob(learned, "hook_hints", hints, f"permutasyon testi + FDR<={FDR_Q}, CI sifiri icermiyor, eski/yeni yari ayni yon, her grupta n>={MIN_N}"):
        changed.append("hook_hints")
    topics = []
    for f in findings:
        if f["kind"] == "format" and f["verdict"] == "pozitif":
            topics.append({"format": f["feature"].split("=", 1)[1], "diff": f["diff"], "ci": f["ci"], "n": [f["n_with"], f["n_without"]]})
    if _set_knob(learned, "topic_hints", topics, f"format medyan farki: permutasyon + FDR<={FDR_Q}, CI>0"):
        changed.append("topic_hints")
    dr = duration_range(rows)
    if _set_knob(learned, "duration_sec_range", dr, "tutmasi en iyi 1/3 videonun sure p25-p75 (n>=9); yeterli veri yoksa temizlenir"):
        changed.append("duration_sec_range")
    learned["updated"] = time.strftime("%Y-%m-%d %H:%M")
    learned["n_videos"] = len(rows)
    learned["hard_rules_untouched"] = list(HARD_RULES)
    _js(LEARNED_FILE, learned)
    return learned, changed


# ------------------------------------------------------------------ tuketiciler (prompt + preflight)
def prompt_context():
    """AURA prompt'larina eklenen kisa, YUMUSAK ipucu bloku. Kanit yoksa bos string."""
    L = _jl(LEARNED_FILE, {})
    parts = [h["text"] for h in L.get("hook_hints", [])]
    parts += [f"The '{t['format']}' format has outperformed the channel median" for t in L.get("topic_hints", [])]
    if L.get("duration_sec_range"):
        a, b = L["duration_sec_range"]
        parts.append(f"The best-retaining videos ran about {a}-{b} seconds")
    if not parts:
        return ""
    return ("\n\nDATA-DERIVED HINTS (soft, from this channel's own stats; small sample; they NEVER override the hard rules "
            "- English only, no invented facts, no invented numbers):\n- " + "\n- ".join(parts) + "\n")


def soft_checks(en_text, est_sec):
    """preflight'a opsiyonel (ok=None/True) kontroller eklemek icin: (ok, label, detail) listesi."""
    L = _jl(LEARNED_FILE, {})
    out = []
    dr = L.get("duration_sec_range")
    if dr:
        out.append((True if dr[0] - 3 <= est_sec <= dr[1] + 3 else None,
                    f"Ogrenilen sure araligi {dr[0]}-{dr[1]} sn (yumusak ipucu)", f"tahmini ~{est_sec} sn"))
    return out


# ------------------------------------------------------------------ rapor ve calistirma
COVERAGE_NOTE = ("CTR / gosterim: YouTube Analytics API vermiyor. YouTube Studio > Analiz > Verileri indir CSV'sini panelden "
                 "aktar (haftada bir yeterli). Ilk 2-3 saniye tutmasi: audienceWatchRatio API'sinden denenir; yetki/kota yoksa bos kalir.")


def report_md(rows, findings, learned, changed):
    have = lambda k: sum(1 for r in rows if r.get(k) is not None)
    lines = [f"# Ogrenme raporu - {time.strftime('%Y-%m-%d %H:%M')}", "",
             "## Veri kapsami",
             f"- Video: {len(rows)} · 48s/olgun izlenme: {have('outcome_views')} · retention: {have('retention')} · "
             f"ilk %10 tutma: {have('early_ret')} · CTR: {have('ctr')} · script kayitli (kanca/dongu ozellikleri): {have('hook_words')}",
             f"- {COVERAGE_NOTE}", "",
             "## Ne degisti" if changed else "## Ne degisti: HICBIR SEY (kanit esigi gecilmedi - bu normal)"]
    for c in changed:
        lines.append(f"- `{c}` -> {learned.get(c)}")
    sig = [f for f in findings if f["verdict"] in ("pozitif", "negatif")]
    lines += ["", f"## Istatistiksel olarak ayirt edilebilen ozellikler (permutasyon testi + FDR<={FDR_Q}, her grupta n>={MIN_N})"]
    if not sig:
        lines.append("- Yok. Orneklem kucuk; sistem rastgele gurultuyu kural yapmaz.")
    for f in sig:
        lines.append(f"- **{f['feature']}** -> {f['metric_label']}: {f['verdict']} (medyan {f['median_with']} vs {f['median_without']}, "
                     f"CI {f['ci']}, n={f['n_with']}/{f['n_without']})")
    lines += ["", "## Hic dokunulmayan kurallar"] + [f"- {r}" for r in HARD_RULES]
    lines += ["", "_Bu rapor TAHMIN degil; kendi kanal verimizin ozetidir. Tek video/tek hafta sonuc degildir._"]
    return "\n".join(lines)


def run_once(force_fetch=True):
    """Topla -> analiz et -> yumusak ayarlari guncelle -> rapor yaz. Hicbir sey yayinlamaz."""
    rows = collect(fetch_early=force_fetch)
    findings = analyze(rows)
    learned, changed = update_rules(rows, findings)
    text = report_md(rows, findings, learned, changed)
    os.makedirs(REPORT_DIR, exist_ok=True)
    name = "ogrenme_" + time.strftime("%Y-%m-%d_%H%M") + ".md"
    open(os.path.join(REPORT_DIR, name), "w", encoding="utf-8").write(text)
    open(RUN_MARK, "w").write(str(time.time()))
    return {"ok": True, "report": name, "text": text, "changed": changed, "n_videos": len(rows)}


def run_daily():
    """Panel arka plan dongusu cagirir; en fazla 20 saatte bir calisir."""
    try:
        if time.time() - float(open(RUN_MARK).read()) < 20 * 3600:
            return {"skipped": True}
    except Exception:
        pass
    return run_once()
