"""Buyume makinesi: format etiketleri + format karsilastirma + yayin oncesi kontrol (kural tabanli).
Hicbir sey yayinlamaz/gondermez. 'Skor' bir TAHMIN degil, kurallara uyum ozetidir."""
import difflib
import json
import os
import re
import statistics as S
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TAGS_FILE = os.path.join(HERE, "video_tags.json")
REPORT_DIR = os.path.join(HERE, "reports")

FORMATS = {
    "transparency": "Seffaflik (gercek rakamlar / AI kendi deneyini anlatir)",
    "template": "Sablon / prompt cerceve",
    "identity": "Kimlik-tehdit (Trap, Mirror, Replaced...)",
    "directive": "Emir kipi (Stop ...)",
    "agenda": "Gundem / haber yorumu (gercek, dogrulanmis AI olaylari)",
    "verdict": "Hype or Real? serisi (iddia + kanit + Aura'nin karari)",
    "other": "Diger",
}


def auto_format(title):
    t = title.lower()
    if t.startswith("hype or real"):
        return "verdict"
    if re.search(r"real numbers|my numbers|what i learned", t):
        return "transparency"
    if re.search(r"prompt|framework|matrix|anchor|persona|pareto|template|checklist", t):
        return "template"
    if re.search(r"trap|mirror|replaced|fake|yes-man|validation|fear", t):
        return "identity"
    if t.startswith("stop") or re.search(r"\| stop", t):
        return "directive"
    if re.search(r"\bceo\b|openai|anthropic|deepmind|\bxai\b|announc|launch(ed)?|warn(s|ed|ing)?|resign|slow ?down|regulat", t):
        return "agenda"
    return "other"


def tags_load():
    try:
        return json.load(open(TAGS_FILE, encoding="utf-8"))
    except Exception:
        return {}


def tag_set(video_id, fmt):
    if fmt not in FORMATS:
        raise ValueError("Gecersiz format.")
    d = tags_load()
    d[video_id] = fmt
    json.dump(d, open(TAGS_FILE, "w", encoding="utf-8"), indent=1)


def format_stats(stats, analytics_rows=None):
    """stats: insights.channel_stats(); analytics_rows: insights.analytics_report()['rows'] veya None."""
    saved = tags_load()
    ret = {r["video_id"]: r["avg_pct"] for r in (analytics_rows or [])}
    groups = {}
    vids = []
    for v in stats["videos"]:
        fmt = saved.get(v["id"]) or auto_format(v["title"])
        vids.append({"id": v["id"], "title": v["title"], "format": fmt, "auto": v["id"] not in saved,
                     "views": v["views"], "likes": v["likes"], "retention": ret.get(v["id"])})
        groups.setdefault(fmt, []).append(vids[-1])
    out = []
    for fmt, items in groups.items():
        views = [i["views"] for i in items]
        rets = [i["retention"] for i in items if i["retention"] is not None]
        n = len(items)
        out.append({"format": fmt, "label": FORMATS[fmt], "n": n, "median_views": S.median(views),
                    "mean_views": round(S.mean(views), 1), "max_views": max(views),
                    "median_retention": round(S.median(rets), 1) if rets else None,
                    "verdict": "yetersiz ornek (n<5): sadece fikir, sonuc degil" if n < 5 else "n>=5: hala kucuk, dikkatli yorumla"})
    out.sort(key=lambda g: -g["median_views"])
    return {"groups": out, "videos": vids}


def _words(s):
    return re.findall(r"[A-Za-z0-9']+", s)


def _sentences(s):
    return [x for x in re.split(r"(?<=[.!?])\s+", s.strip()) if x]


HYPE = re.compile(r"guarantee|millionaire|get rich|make \$|\bviral\b|100%|secret|hack that|overnight", re.I)
GENERIC_OPEN = re.compile(
    r"^(hi|hey|hello)\b|^today,? i('m| am| will)?\b|^in this video\b|^let'?s talk about\b|"
    r"^let me tell you\b|^so,? today\b|^welcome back\b|^i want to talk about\b|^i'?m going to (show|talk|tell)\b",
    re.I)
# 2026-10-10: abone donusumu testi - kanalin ne oldugunu adlandiran "Follow" cumlesi
_VERDICT = re.compile(r"^\s*(?:my\s+)?verdict\s*[:\-]\s*(real|hype|unclear)\b", re.I)
FOLLOW_CTA = re.compile(r"\bfollow\b.{0,60}\b(every|daily|each)\b", re.I)
_LOOP_STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "your", "you", "ai", "stop", "aura",
              "day", "why", "how", "is", "are", "my", "it", "with", "without", "not", "that", "this",
              "so", "tell", "me", "below", "comment"}


def preflight(title, en_text, tr_text, description, existing_titles, median_views=None):
    checks = []

    def add(ok, label, detail=""):
        checks.append({"ok": ok, "label": label, "detail": detail})

    en = (en_text or "").strip()
    sents = _sentences(en)
    words = _words(en)
    est_sec = round(len(words) / 2.6, 1)  # ~2.6 kelime/sn (Aura TTS hizina yakin kaba tahmin)
    add(len(title) <= 35 and len(title) > 0, "Baslik <= 35 karakter", f"{len(title)} karakter")
    add(not re.search(r"[\U0001F300-\U0001FAFF#]", title), "Baslikta emoji/hashtag yok")
    add(not re.search(r"[çğıöşüÇĞİÖŞÜ]", en), "Ingilizce scriptte Turkce karakter yok")
    if sents:
        first = len(_words(sents[0]))
        add(first <= 12, "Kanca: ilk cumle <= 12 kelime", f"{first} kelime: {sents[0][:60]}")
        add(GENERIC_OPEN.search(sents[0].strip()) is None, "Jenerik acilis yok ('today I'll', 'hi everyone'...)",
            sents[0][:60])
        add(sents[-1].strip().endswith("?") or re.search(r"comment|tell me|below|reply|let me know|drop ", sents[-1], re.I) is not None,
            "Sonda soru / yorum cagrisi var", sents[-1][:70])
        if len(sents) >= 2:
            first_w = {w.lower() for w in _words(sents[0])} - _LOOP_STOP
            last_w = {w.lower() for w in _words(sents[-1])} - _LOOP_STOP
            shared = first_w & last_w
            add(None if not shared else True, "Dongu: kapanis acilisa bagliyor mu (opsiyonel, guclu sinyal)",
                (f"ortak: {sorted(shared)}" if shared else "ortak kelime yok - kapanisi acilisa bagla (loop teknigi)"))
        add(all(len(x) <= 72 for x in sents), "Her cumle <= 72 karakter (CC guvenligi)",
            f"en uzun: {max(len(x) for x in sents)}")
        fol = [x for x in sents[:-1] if FOLLOW_CTA.search(x)]
        add(None if not (fol or FOLLOW_CTA.search(sents[-1])) else bool(fol),
            "Abone testi: kanali adlandiran 'Follow' cumlesi sondan bir onceki cumlede (opsiyonel)",
            ("var: " + fol[0][:60]) if fol else (
                "son cumlede - dongu/soru son cumle kalmali, Follow cumlesini bir onceye al" if FOLLOW_CTA.search(sents[-1])
                else "yok - ornek: 'Follow - I cover one real AI story like this every day.'"))
    else:
        add(False, "Script bos")
    add(12 <= est_sec <= 28, "Tahmini sure 12-28 sn", f"~{est_sec} sn ({len(words)} kelime)")
    # 2026-10-14 hipotez (n=14, YouTube 28 gun): 0:28-0:29 videolarin 3/4'u %23-36 izlenme yuzdesi, 0:20-0:26 genelde >%40. Bloklamaz.
    add(None if est_sec > 26 else True, "Kisa sure ipucu: <=26 sn (hipotez, n=14; 29 sn'likler en zayif tutmayi verdi)", f"~{est_sec} sn")
    if tr_text and tr_text.strip():
        tr_sents = _sentences(tr_text)
        add(len(tr_sents) == len(sents), "EN/TR cumle sayisi esit", f"EN {len(sents)} / TR {len(tr_sents)}")
        if tr_sents:
            add(all(len(x) <= 72 for x in tr_sents), "Her TR cumle <= 72 karakter (CC guvenligi)",
                f"en uzun: {max(len(x) for x in tr_sents)}" + (
                    " - uzun TR cumle otomatik bolununce EN/TR cumle sayisi kayar ve TR CC yayindan "
                    "SONRA sessizce basarisiz olabilir, yayindan once kisalt" if max(len(x) for x in tr_sents) > 72 else ""))
    else:
        add(None, "Turkce CC yok (opsiyonel)")
    # "Hype or Real?" serisi (2026-10-10): karar cumlesi + kanit yapisi
    vi = next((i for i, x in enumerate(sents) if _VERDICT.match(x)), None)
    if title.lower().startswith("hype or real") or vi is not None:
        add(vi is not None and 0 < vi < len(sents) - 1, "Seri: 'Verdict: REAL|HYPE|UNCLEAR.' cumlesi var ve son cumle degil",
            "yok - ornek: 'Verdict: UNCLEAR.'" if vi is None else f"cumle {vi + 1}/{len(sents)}")
        if vi is not None:
            add(vi >= 4, "Seri: kararin onunde en az 2 kanit cumlesi (hook + soru + 2 kanit)", f"karardan once {vi} cumle (kanit: {max(vi - 2, 0)})")
            add(re.search(r"\b(reports|reported|according to|told|said|says|per)\b", " ".join(sents[2:vi]), re.I) is not None,
                "Seri: kanit cumlelerinde kaynak atfi var (reports/says/told/according to)", "kaynak atfi bulunamadi - 'the FT reports' gibi ekle")
            add(vi == 0 or not re.search(r"\b(REAL|HYPE|UNCLEAR)\b", " ".join(sents[:vi])), "Seri: karar kelimesi kararin onunde sizmamis", "")
    add(not HYPE.search(en + " " + (description or "") + " " + title), "Abartili vaat / garanti dili yok")
    nums = re.findall(r"\b\d[\d,.]*\b", en)
    add(None if nums else True, "Rakam iceriyorsa dogrulanabilir olmali", (", ".join(nums[:6]) + " -> kaynagi (analitik) dogrula") if nums else "rakam yok")
    add("ai" in (description or "").lower() or "i'm an ai" in en.lower() or "i am an ai" in en.lower(),
        "AI oldugu acik (script ya da aciklama)")
    core = lambda t: re.sub(r"^\s*hype or real\s*[:\-]\s*", "", t, flags=re.I)  # seri oneki ortak kelime sayilmaz (her bolum "Hype or Real:" ile baslar)
    tl = core(title).lower().strip()
    best = max(((difflib.SequenceMatcher(None, tl, core(e).lower()).ratio(), e) for e in existing_titles), default=(0, ""))
    add(best[0] < 0.6, "Mevcut bir videoyla ayni konu degil", f"en benzer: '{best[1]}' ({round(best[0] * 100)}%)" if best[1] else "")
    claim = re.search(r"I (can |will |always |never )?(process|perform|analy[sz]e|learn|improve|feel|understand|remember|know|think)|my (model|training|algorithm)|without (human )?bias|each video improves|grow without", en, re.I)
    add(claim is None, "Aura kendi yetenegi/ogrenmesi hakkinda dogrulanamayan iddia yok",
        (f"bulundu: '{claim.group(0)}'" if claim else ""))
    over = re.search(r"(immediately|instantly|always|never|guaranteed|100 ?percent|zero)", en, re.I)
    add(None if over else True, "Mutlak/abartili kelime yok (immediately, always, never, zero...)",
        (f"'{over.group(0)}' - kanitlayabiliyor musun?" if over else ""))
    stop = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "your", "you", "ai", "stop", "aura", "day", "why", "how", "is", "are", "my", "it", "with", "without", "not"}
    cw = lambda s: {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in stop and len(w) > 1}
    mine = cw(core(title))
    hit = next(((e, mine & cw(core(e))) for e in existing_titles if len(mine & cw(core(e))) >= 2), None)
    add(hit is None, "Konu anahtar kelimeleri mevcut bir videoyla cakismiyor", (f"'{hit[0]}' ile ortak: {sorted(hit[1])}" if hit else ""))
    try:  # ogrenilmis YUMUSAK ipuclari (learner.py): ok None/True olabilir, ASLA False (bloklamaz)
        import learner
        for ok, label, detail in learner.soft_checks(en, est_sec):
            add(ok, label, detail)
    except Exception:
        pass
    ok_n = sum(1 for c in checks if c["ok"] is True)
    tot = sum(1 for c in checks if c["ok"] is not None)
    return {"checks": checks, "score": ok_n, "of": tot, "est_seconds": est_sec, "baseline_median_views": median_views,
            "note": "Bu bir izlenme TAHMINI degil; kurallara uyum ozetidir."}


def reports_list():
    if not os.path.isdir(REPORT_DIR):
        return []
    return sorted(os.listdir(REPORT_DIR), reverse=True)


def report_save(text):
    os.makedirs(REPORT_DIR, exist_ok=True)
    name = time.strftime("%Y-%m-%d_%H%M") + ".md"
    open(os.path.join(REPORT_DIR, name), "w", encoding="utf-8").write(text)
    return name


def report_read(name):
    name = os.path.basename(name)
    return open(os.path.join(REPORT_DIR, name), encoding="utf-8").read()


def report_age_days():
    lst = reports_list()
    if not lst:
        return None
    return (time.time() - os.path.getmtime(os.path.join(REPORT_DIR, lst[0]))) / 86400


# =====================================================================
# 2026-09-26: deneyler, taslaklar, aksiyon kuyrugu (Aura onerir, operator "Uygula" der)
# =====================================================================
import calendar
import uuid

EXP_FILE = os.path.join(HERE, "experiments.json")
DRAFT_FILE = os.path.join(HERE, "drafts.json")
ACTION_FILE = os.path.join(HERE, "actions.json")


def _jl(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def _js(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _pub_epoch(s):  # "YYYY-MM-DD HH:MM" (UTC) -> epoch
    return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))


# ---- deneyler ----
def exp_add(name, hypothesis, fmt, target_n, baseline_median):
    if fmt not in FORMATS:
        raise ValueError("Gecersiz format.")
    target_n = max(2, min(int(target_n), 20))
    rows = _jl(EXP_FILE, [])
    rows.append({"id": uuid.uuid4().hex[:8], "name": str(name)[:80], "hypothesis": str(hypothesis)[:300], "format": fmt,
                 "target_n": target_n, "baseline_median": baseline_median, "created": time.strftime("%Y-%m-%d %H:%M"),
                 "created_ts": time.time()})
    _js(EXP_FILE, rows)
    return rows[-1]


def exp_delete(eid):
    _js(EXP_FILE, [e for e in _jl(EXP_FILE, []) if e["id"] != eid])


def exp_eval_all(stats):
    saved = tags_load()
    out = []
    for e in _jl(EXP_FILE, []):
        members = []
        for v in stats["videos"]:
            fmt = saved.get(v["id"]) or auto_format(v["title"])
            if fmt != e["format"]:
                continue
            ep = _pub_epoch(v["published"])
            if ep >= e["created_ts"] - 3 * 3600:  # yayin saati UTC, kucuk tolerans
                members.append((v, (time.time() - ep) / 86400))
        mature = [v for v, age in members if age >= 2]
        views = [v["views"] for v in mature]
        med = S.median(views) if views else None
        base = e["baseline_median"] or 0
        if len(mature) < e["target_n"]:
            verdict = f"toplaniyor: {len(mature)}/{e['target_n']} olgun video (>=2 gunluk)"
        elif med is None or base == 0:
            verdict = "belirsiz"
        elif med >= base * 1.5:
            verdict = f"kanal baz medyaninin belirgin USTUNDE ({med} vs {base}); yine de kucuk ornek, kanit degil"
        elif med <= base * 0.67:
            verdict = f"baz medyanin ALTINDA ({med} vs {base}); yine de kucuk ornek"
        else:
            verdict = f"belirgin fark yok ({med} vs {base})"
        out.append({**e, "count": len(members), "mature": len(mature), "median_views": med, "verdict": verdict,
                    "videos": [v["title"] for v, _ in members]})
    return out


# ---- taslaklar ----
def draft_add(d):
    rows = _jl(DRAFT_FILE, [])
    row = {"id": uuid.uuid4().hex[:8], "title": str(d.get("title", ""))[:60], "en_script": str(d.get("en_script", "")),
           "tr_script": str(d.get("tr_script", "")), "description": str(d.get("description", "")),
           "tags": str(d.get("tags", "")), "format": d.get("format") if d.get("format") in FORMATS else "other",
           "rationale": str(d.get("rationale", ""))[:300], "preflight": d.get("preflight"),
           "status": "taslak", "video": None, "srt": None, "link": None, "created": time.strftime("%Y-%m-%d %H:%M")}
    rows.append(row)
    _js(DRAFT_FILE, rows[-60:])
    return row


def drafts_list():
    return _jl(DRAFT_FILE, [])


def draft_get(did):
    return next((d for d in drafts_list() if d["id"] == did), None)


def draft_update(did, **fields):
    rows = drafts_list()
    for d in rows:
        if d["id"] == did:
            d.update(fields)
    _js(DRAFT_FILE, rows)


def draft_delete(did):
    _js(DRAFT_FILE, [d for d in drafts_list() if d["id"] != did])


# ---- aksiyon kuyrugu ----
def actions_add(items):
    rows = _jl(ACTION_FILE, [])
    added = []
    for it in items:
        it = dict(it)
        it["id"] = uuid.uuid4().hex[:8]
        it["status"] = "bekliyor"
        it["created"] = time.strftime("%Y-%m-%d %H:%M")
        rows.append(it)
        added.append(it)
    _js(ACTION_FILE, rows[-80:])
    return added


def actions_list(status=None):
    rows = _jl(ACTION_FILE, [])
    return [r for r in rows if status is None or r["status"] == status]


def action_set(aid, status, result=""):
    rows = _jl(ACTION_FILE, [])
    for r in rows:
        if r["id"] == aid:
            r["status"] = status
            r["result"] = result
    _js(ACTION_FILE, rows)


def action_get(aid):
    return next((r for r in _jl(ACTION_FILE, []) if r["id"] == aid), None)


def format_stats_full(stats, analytics_rows, tt_latest):
    """format_stats + TikTok (elle girilen) ozetleri; tt_latest: {youtube_video_id: {views,likes,comments,shares}}"""
    base = format_stats(stats, analytics_rows)
    fmt_of = {v["id"]: v["format"] for v in base["videos"]}
    tt = {}
    for vid, r in tt_latest.items():
        f = fmt_of.get(vid)
        if f:
            tt.setdefault(f, []).append(r)
    for g in base["groups"]:
        rows = tt.get(g["format"], [])
        g["tt_n"] = len(rows)
        g["tt_median_views"] = S.median([r["views"] for r in rows]) if rows else None
        g["tt_median_likes"] = S.median([r["likes"] for r in rows]) if rows else None
    for v in base["videos"]:
        r = tt_latest.get(v["id"])
        v["tt"] = ({"views": r["views"], "likes": r["likes"], "comments": r["comments"], "shares": r["shares"], "date": r["date"]} if r else None)
    return base
