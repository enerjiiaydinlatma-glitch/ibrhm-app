"""Sistem taramasi (2026-11-27): kanca, ses, ilk gorsel, etkilesim, konu - KODLA olculebilen sayilar + konseye (gorselli) gidecek ozet.
Hicbir sey uydurmaz: olculemeyen alan 'veri yok' diye isaretlenir; orneklem kucuktur, sonuclar hipotezdir."""
import base64
import io
import json
import os
import re
import statistics
import subprocess

_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **_NOWIN)


def duration(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    try:
        return round(float(r.stdout.strip()), 2)
    except Exception:
        return None


def audio_stats(path):
    """Ortalama/tepe ses seviyesi (dB), basta sessizlik (sn). Kanca icin: ilk sesin gecikmesi izleyiciyi kaybettirir."""
    out = {"mean_db": None, "max_db": None, "lead_silence_s": None}
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "volumedetect,silencedetect=noise=-38dB:d=0.15", "-f", "null", "-"])
    t = r.stderr
    m1 = re.search(r"mean_volume:\s*(-?[\d.]+) dB", t)
    m2 = re.search(r"max_volume:\s*(-?[\d.]+) dB", t)
    if m1:
        out["mean_db"] = float(m1.group(1))
    if m2:
        out["max_db"] = float(m2.group(1))
    # basta sessizlik: ilk silence_start ~0 ise onu izleyen silence_end
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", t)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", t)]
    if starts and starts[0] <= 0.05 and ends:
        out["lead_silence_s"] = round(ends[0], 2)
    else:
        out["lead_silence_s"] = 0.0
    return out


def words(text):
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def extract_frame(video, t, out_path, width=360):
    _run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", f"scale={width}:-1", out_path])
    return out_path if os.path.exists(out_path) else None


def frame_stats(img_path):
    from PIL import Image, ImageStat
    im = Image.open(img_path).convert("RGB")
    g = im.convert("L")
    st = ImageStat.Stat(g)
    rg = ImageStat.Stat(im)
    # renk cesitliligi (basit): kanal std ortalamasi
    return {"brightness": round(st.mean[0], 1), "contrast": round(st.stddev[0], 1), "color_spread": round(sum(rg.stddev) / 3, 1),
            "size": list(im.size)}


def contact_sheet(items, cell=300):
    """items: [(etiket, resim_yolu)] -> tek JPEG (base64). Modellere TEK gorsel olarak gider."""
    from PIL import Image, ImageDraw
    items = [(a, b) for a, b in items if b and os.path.exists(b)]
    if not items:
        return None
    cols = min(3, len(items))
    rows = (len(items) + cols - 1) // cols
    ims = []
    for lab, pth in items:
        im = Image.open(pth).convert("RGB")
        im.thumbnail((cell, int(cell * 16 / 9)))
        ims.append((lab, im))
    ch = max(i.size[1] for _, i in ims) + 22
    sheet = Image.new("RGB", (cols * cell, rows * ch), (14, 18, 31))
    d = ImageDraw.Draw(sheet)
    for k, (lab, im) in enumerate(ims):
        x, y = (k % cols) * cell, (k // cols) * ch
        sheet.paste(im, (x + (cell - im.size[0]) // 2, y + 20))
        d.text((x + 6, y + 4), str(lab)[:40], fill=(200, 190, 255))
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def first_sentence(text):
    m = re.match(r"\s*(.+?[.?!])(\s|$)", text or "")
    return (m.group(1) if m else (text or "")).strip()


def hook_row(title, en_script):
    fs = first_sentence(en_script)
    return {"title": title, "first": fs, "words": words(fs), "question": fs.endswith("?"), "number": bool(re.search(r"\d", fs)),
            "invite": fs.lower().startswith("come inside"), "ai_first": bool(re.search(r"\bI'm Aura\b|\bAn AI\b", fs, re.I))}


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def hook_findings(rows):
    """rows: hook_row + {'views','avg_pct'}. Gruplari karsilastirir; n kucukse acikca soyler."""
    out = []
    def cmp(label, key):
        a = [r for r in rows if r[key]]
        b = [r for r in rows if not r[key]]
        if len(a) >= 2 and len(b) >= 2:
            out.append(f"{label}: n={len(a)} medyan izlenme {_med([r['views'] for r in a])} / tutma {_med([r['avg_pct'] for r in a])}%  |  diger n={len(b)} medyan izlenme {_med([r['views'] for r in b])} / tutma {_med([r['avg_pct'] for r in b])}%")
        else:
            out.append(f"{label}: karsilastirma icin yeterli veri yok (n={len(a)} / {len(b)})")
    cmp("Ilk cumle SORU", "question")
    cmp("Ilk cumle RAKAM iceriyor", "number")
    cmp("Ilk cumle 'Come inside' daveti", "invite")
    short = [r for r in rows if r["words"] <= 6]
    long_ = [r for r in rows if r["words"] > 6]
    if len(short) >= 2 and len(long_) >= 2:
        out.append(f"Ilk cumle <=6 kelime: n={len(short)} medyan izlenme {_med([r['views'] for r in short])} | >6 kelime: n={len(long_)} medyan {_med([r['views'] for r in long_])}")
    return out


def voice_findings(stats):
    out = []
    ok = [s for s in stats if s.get("wps")]
    if ok:
        out.append(f"Konusma hizi: {_med([s['wps'] for s in ok])} kelime/sn (medyan, n={len(ok)}); Shorts icin tipik aralik ~2.3-3.2 (bu bir kural degil, kaba referans)")
    ls = [s["lead_silence_s"] for s in stats if s.get("lead_silence_s") is not None]
    if ls:
        out.append(f"Videonun basinda sessizlik: medyan {_med(ls)} sn, en uzun {max(ls)} sn" + (" -> ilk sesin gecikmesi kanca icin riskli" if max(ls) > 0.6 else ""))
    md = [s["mean_db"] for s in stats if s.get("mean_db") is not None]
    if md:
        out.append(f"Ortalama ses seviyesi: medyan {_med(md)} dB (cok dusukse (<-24 dB) telefonda zayif duyulur)")
    return out


def build_report(videos, scripts, outcomes, workdir):
    """videos: [{'title','path'}]; scripts: {title: en_script}; outcomes: {title: {'views','avg_pct','likes','comments','tt_views','tt_shares'}}.
    Doner: {'dims': {...}, 'sheet_b64': str|None, 'text': str}"""
    os.makedirs(workdir, exist_ok=True)
    vstats, frames = [], []
    for i, v in enumerate(videos):
        p = v["path"]
        s = {"title": v["title"], "duration": duration(p)}
        s.update(audio_stats(p))
        sc = scripts.get(v["title"], "")
        s["wps"] = round(words(sc) / s["duration"], 2) if s["duration"] and sc else None
        f1 = extract_frame(p, 0.3, os.path.join(workdir, f"f{i}_a.jpg"))
        if f1:
            s["first_frame"] = frame_stats(f1)
            frames.append((v["title"][:30], f1))
        vstats.append(s)
    hrows = []
    for t, sc in scripts.items():
        h = hook_row(t, sc)
        o = outcomes.get(t) or {}
        h["views"], h["avg_pct"] = o.get("views"), o.get("avg_pct")
        hrows.append(h)
    measured = [r for r in hrows if r["views"] is not None]
    tot = list(outcomes.values())
    likes = sum(o.get("likes") or 0 for o in tot)
    comments = sum(o.get("comments") or 0 for o in tot)
    views = sum(o.get("views") or 0 for o in tot)
    shares = sum(o.get("tt_shares") or 0 for o in tot)
    dims = {
        "kanca": {"rows": [{k: r[k] for k in ("title", "first", "words", "views", "avg_pct")} for r in measured][:20], "findings": hook_findings(measured)},
        "ses": {"rows": [{k: s.get(k) for k in ("title", "duration", "wps", "lead_silence_s", "mean_db", "max_db")} for s in vstats], "findings": voice_findings(vstats)},
        "ilk_gorsel": {"rows": [{"title": s["title"], **(s.get("first_frame") or {})} for s in vstats], "findings": [
            "Ilk kare istatistikleri (parlaklik 0-255, kontrast, renk yayilimi). Kapak/ilk karenin gucunu YAPAY ZEKA GORSEL analizi (konsey) degerlendirir; sayilar tek basina karar vermez."]},
        "etkilesim": {"findings": [f"Toplam (taranan videolar): {views} izlenme, {likes} begeni, {comments} yorum, TikTok paylasim {shares}.",
                                   (f"Begeni/izlenme {round(100 * likes / views, 2)}%, yorum/izlenme {round(100 * comments / views, 2)}%" if views else "izlenme verisi yok")]},
    }
    lines = []
    for k, d in dims.items():
        lines.append(f"## {k.upper()}")
        lines += ["- " + f for f in d["findings"]]
        for r in d.get("rows", [])[:12]:
            lines.append("  " + json.dumps(r, ensure_ascii=False))
    return {"dims": dims, "sheet_b64": contact_sheet(frames), "text": "\n".join(lines), "n_videos": len(vstats)}
