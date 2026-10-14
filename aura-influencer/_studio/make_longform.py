"""Uzun video yapicisi (2026-10-14): "Hype or Real: Haftanin Skor Tablosu" gibi 5-10 dk'lik 16:9 videolar.

Shorts yapicisindan (make_video.py: dalga + altyazi) FARKLI: her cumle icin ekranda KAYNAK ATIFLI kanit karti,
karar damgasi, skor tablosu, ilerleme cubugu. Amac: sablonlu/otomatik "yuzsuz" icerikten ayrisan, ozgun analiz.

Akis: script.json -> check_script (kurallar) -> sahne basina TTS -> kartlar (PIL) -> sahne mp4 (ffmpeg) -> birlestir.
Ciktilar: mp4, TR .srt (Turkce CC GARANTISI icin, cumle-cumle gercek sure), EN .srt, aciklama (bolumler + kaynaklar).
Hicbir sey yayinlamaz.  Kullanim (ses motoru calisirken, AURA_VOICE_KEY env):
    python make_longform.py longform/scoreboard_001.json --out output/aura_scoreboard1.mp4
    python make_longform.py longform/scoreboard_001.json --preview onizleme   (ses yok, sahne basina bir kare)
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from subtitles import build_srt  # noqa: E402

W, H = 1920, 1080
FPS = 25
PAD_SEC = 0.45          # sahne sonu nefes payi
WORDS_PER_SEC = 2.6     # sure tahmini (Shorts ile ayni kaba hiz)
MIN_EST_SEC, MAX_EST_SEC = 180, 720   # kural: tahmini sure 3-12 dk (testler gevsetebilir)
VERDICTS = ("REAL", "HYPE", "UNCLEAR")
VCOLOR = {"REAL": (63, 185, 80), "HYPE": (240, 136, 62), "UNCLEAR": (210, 153, 34)}
BG_TOP, BG_BOT = (11, 7, 16), (26, 16, 48)
ACCENT = (124, 176, 255)
WHITE, DIM, MUTED = (240, 240, 245), (120, 120, 140), (160, 160, 180)
TR_CHARS = set("çğıöşüÇĞİÖŞÜ")


# ------------------------------------------------------------------ script kontrolu
def _scene_sents(sc):
    return sc.get("sentences", [])


def check_script(script):
    """Yayindan ONCE kural kontrolu. [(ok, etiket, detay)]; ok False = engel, None = bilgi."""
    out = []

    def add(ok, label, detail=""):
        out.append((ok, label, detail))

    scenes = script.get("scenes", [])
    kinds = [s.get("kind") for s in scenes]
    sents = [x for s in scenes for x in _scene_sents(s)]
    en_words = sum(len(x["en"].split()) for x in sents)
    add(bool(scenes) and kinds[0] == "title" and kinds[-1] == "outro", "Yapi: title ile baslar, outro ile biter", str(kinds[:2] + kinds[-1:]))
    add(all(len(_scene_sents(s)) > 0 for s in scenes), "Her sahnede en az bir cumle")
    bad_tr = [i for i, x in enumerate(sents) if not x.get("tr", "").strip()]
    add(not bad_tr, "Her EN cumlenin TR karsiligi var (Turkce CC garantisi)", f"eksik: {bad_tr[:5]}" if bad_tr else "")
    add(not any(set(x["en"]) & TR_CHARS for x in sents), "EN metinde Turkce karakter yok")
    claims = [s for s in scenes if s.get("kind") == "claim"]
    verdicts = [s for s in scenes if s.get("kind") == "verdict"]
    add(len(claims) >= 3 and len(claims) == len(verdicts), "Her iddianin bir karari var (iddia sayisi >= 3)", f"{len(claims)} iddia / {len(verdicts)} karar")
    add(all(v.get("verdict") in VERDICTS for v in verdicts), "Kararlar REAL / HYPE / UNCLEAR", str([v.get("verdict") for v in verdicts]))
    # kanit cumlelerinde kaynak etiketi
    ev = [x for s in scenes if s.get("kind") == "evidence" for x in _scene_sents(s)]
    facts = [x for x in ev if x.get("role") not in ("why", "change")]   # why/change = editoryal yorum, kanit degil
    nosrc = [x["en"][:40] for x in facts if not x.get("source", "").strip()]
    add(bool(facts) and not nosrc, "Her KANIT cumlesinde KAYNAK etiketi var (editoryal 'why/change' haric)", f"kaynaksiz: {nosrc[:2]}" if nosrc else f"{len(facts)} kanit cumlesi")
    per_claim = [sum(1 for x in _scene_sents(s) if x.get("role") not in ("why", "change")) for s in scenes if s.get("kind") == "evidence"]
    add(all(n >= 3 for n in per_claim), "Her iddiada en az 3 kaynakli kanit cumlesi", str(per_claim))
    add(all(any(x.get("role") == "change" for x in _scene_sents(s)) for s in scenes if s.get("kind") == "evidence"),
        "Her iddiada 'kararimi ne degistirir' cumlesi (yanilma payini acikla)")
    # karar kelimesi kararin onunde sizmamis
    leak = [s.get("n") for s in scenes if s.get("kind") in ("claim", "evidence") and
            re.search(r"(^|\.\s)verdict\s*[:\-]\s*(real|hype|unclear)", " ".join(x["en"] for x in _scene_sents(s)), re.I)]
    add(not leak, "Karar cumlesi sadece karar sahnesinde", str(leak) if leak else "")
    # skor tablosu karar sayilariyla uyumlu
    sb = next((s for s in scenes if s.get("kind") == "scoreboard"), None)
    if sb:
        want = [v.get("verdict") for v in verdicts]
        add(sb.get("rows_verdicts") == want, "Skor tablosu kararlarla ayni", f"tablo {sb.get('rows_verdicts')} / kararlar {want}")
    else:
        add(False, "Skor tablosu sahnesi var")
    add(any(re.search(r"\bfollow\b.{0,60}\b(every|daily|each)\b", x["en"], re.I) for x in _scene_sents(scenes[-1])) if scenes else False,
        "Outro'da kanalin ne oldugunu adlandiran Follow cumlesi")
    add(not re.search(r"\b(guarantee|millionaire|get rich|overnight|100%)\b", " ".join(x["en"] for x in sents), re.I), "Abartili vaat dili yok")
    est = en_words / WORDS_PER_SEC
    add(None, f"Tahmini sure ~{est / 60:.1f} dk ({en_words} kelime, {len(sents)} cumle)", "5-10 dk hedef; dolgu ile uzatma")
    add(MIN_EST_SEC <= est <= MAX_EST_SEC, f"Tahmini sure {MIN_EST_SEC // 60}-{MAX_EST_SEC // 60} dk araliginda", f"{est / 60:.1f} dk")
    return out


def chapters(script, scene_starts):
    """YouTube bolumleri: ilk bolum 0:00 olmali, en az 3, her biri >=10 sn."""
    lines = []
    for sc, t0 in zip(script["scenes"], scene_starts):
        if sc.get("kind") in ("title", "claim", "scoreboard", "outro"):
            label = {"title": "Intro", "scoreboard": "The scoreboard", "outro": "Your turn"}.get(sc["kind"])
            if sc["kind"] == "claim":
                label = f"Claim {sc.get('n')}: {sc.get('short', sc.get('company', ''))}"
            m, s = divmod(int(t0), 60)
            lines.append(f"{m}:{s:02d} {label}")
    return lines


# ------------------------------------------------------------------ yazi tipleri ve cizim yardimcilari
def _font(size, bold=False):
    from PIL import ImageFont
    cands = (["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if bold else
             ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"])
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _bg():
    from PIL import Image
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        f = y / (H - 1)
        c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * f) for i in range(3))
        for x in range(0, W, 1):
            px[x, y] = c
    return img


_BG_CACHE = {}


def _canvas():
    from PIL import Image
    if "bg" not in _BG_CACHE:
        _BG_CACHE["bg"] = _bg()
    return _BG_CACHE["bg"].copy()


def _chip(d, xy, text, fill, fg=(15, 10, 25), size=34):
    f = _font(size, True)
    tw = d.textlength(text, font=f)
    x, y = xy
    d.rounded_rectangle([x, y, x + tw + 44, y + size + 26], radius=(size + 26) // 2, fill=fill)
    d.text((x + 22, y + 11), text, font=f, fill=fg)
    return x + tw + 44


def _frame_common(d, script, scene, progress):
    d.text((90, 54), script.get("series", "HYPE OR REAL?"), font=_font(40, True), fill=ACCENT)
    tag = ""
    if scene.get("kind") in ("claim", "evidence", "verdict"):
        tag = f"CLAIM {scene.get('n')} / {scene.get('of')}"
    elif scene.get("kind") == "scoreboard":
        tag = "SCOREBOARD"
    if tag:
        f = _font(40, True)
        d.text((W - 90 - d.textlength(tag, font=f), 54), tag, font=f, fill=MUTED)
    d.rectangle([0, H - 10, W, H], fill=(30, 22, 52))
    d.rectangle([0, H - 10, int(W * max(0.0, min(1.0, progress))), H], fill=ACCENT)
    d.text((90, H - 62), "Aura - an AI. Sources on screen.", font=_font(26), fill=DIM)


def render_card(script, scene, idx, progress):
    """sahne + cumle indeksi -> PIL gorseli. idx: sahnedeki gecerli cumle (kanitlar birikir)."""
    from PIL import ImageDraw
    img = _canvas()
    d = ImageDraw.Draw(img)
    _frame_common(d, script, scene, progress)
    kind = scene["kind"]
    sents = _scene_sents(scene)
    cur = sents[idx]
    maxw = W - 2 * 130

    if kind == "title":
        f1 = _font(190, True)
        d.text((W // 2, 300), "HYPE OR REAL?", font=f1, fill=ACCENT, anchor="mm")
        d.text((W // 2, 470), script.get("subtitle", ""), font=_font(60), fill=WHITE, anchor="mm")
        for i, (v, c) in enumerate(VCOLOR.items()):
            _chip(d, (W // 2 - 480 + i * 330, 560), v, c, size=36)
        y = 760
        for ln in _wrap(d, cur["en"], _font(54), maxw):
            d.text((W // 2, y), ln, font=_font(54), fill=WHITE, anchor="mm")
            y += 72
    elif kind == "claim":
        d.text((130, 190), (scene.get("company") or "").upper(), font=_font(46, True), fill=MUTED)
        y = 290
        for ln in _wrap(d, scene["claim"], _font(104, True), maxw):
            d.text((130, y), ln, font=_font(104, True), fill=WHITE)
            y += 130
        _chip(d, (130, y + 40), "THE CLAIM", ACCENT, size=36)
        y += 190
        for ln in _wrap(d, cur["en"], _font(46), maxw):
            d.text((130, y), ln, font=_font(46), fill=MUTED)
            y += 62
    elif kind == "evidence":
        d.text((130, 150), scene["claim"], font=_font(40), fill=MUTED)
        _chip(d, (130, 220), "EVIDENCE", (63, 185, 200), size=36)
        shown = sents[:idx + 1]
        top, avail = 330, H - 100 - 330
        # sigmayi sec: once 3 cumle / buyuk punto, sigmazsa daha az cumle / kucuk punto
        for n_show, cur_pt, old_pt in ((3, 60, 48), (2, 60, 48), (2, 52, 40), (1, 52, 40), (1, 44, 36)):
            win = shown[-n_show:]
            total = 0
            for k, s_ in enumerate(win):
                is_c = (k == len(win) - 1)
                pt = cur_pt if is_c else old_pt
                n_ln = len(_wrap(d, s_["en"], _font(pt, is_c), maxw))
                total += n_ln * int(pt * 1.3) + 40 + (90 if is_c and (s_.get("source") or s_.get("role")) else 0)
            if total <= avail:
                break
        y = top
        for k, s_ in enumerate(win):
            is_c = (k == len(win) - 1)
            pt = cur_pt if is_c else old_pt
            fnt = _font(pt, is_c)
            for ln in _wrap(d, s_["en"], fnt, maxw):
                d.text((130, y), ln, font=fnt, fill=WHITE if is_c else DIM)
                y += int(pt * 1.3)
            if is_c and s_.get("role") in ("why", "change"):
                lab = "WHY IT MATTERS" if s_["role"] == "why" else "WHAT WOULD CHANGE MY VERDICT"
                _chip(d, (130, y + 10), lab, (80, 60, 140), fg=WHITE, size=28)
                y += 90
            elif is_c and s_.get("source"):
                _chip(d, (130, y + 10), "SOURCE", (60, 60, 90), fg=WHITE, size=28)
                d.text((130 + 190, y + 18), s_["source"], font=_font(34), fill=ACCENT)
                y += 90
            y += 40
    elif kind == "verdict":
        v = scene["verdict"]
        col = VCOLOR[v]
        d.rounded_rectangle([330, 200, W - 330, 600], radius=36, outline=col, width=14)
        d.text((W // 2, 290), "VERDICT", font=_font(56, True), fill=col, anchor="mm")
        d.text((W // 2, 450), v, font=_font(180, True), fill=col, anchor="mm")
        y = 690
        for ln in _wrap(d, cur["en"], _font(56), maxw):
            d.text((W // 2, y), ln, font=_font(56), fill=WHITE, anchor="mm")
            y += 74
    elif kind == "scoreboard":
        rows = scene["rows"]
        verdicts = scene["rows_verdicts"]
        counts = {k: verdicts.count(k) for k in VERDICTS}
        x = 130
        for k in VERDICTS:
            x = _chip(d, (x, 170), f"{k} {counts[k]}", VCOLOR[k], size=44) + 28
        y = 290
        pitch = max(110, min(150, (H - 100 - 290 - 190) // max(len(rows), 1)))  # kapanis cumlesine ve footer'a yer birak
        for i, (r, v) in enumerate(zip(rows, verdicts)):
            d.text((130, y), f"{i + 1}.", font=_font(54, True), fill=MUTED)
            lines = _wrap(d, r, _font(54), 1100)
            for j, ln in enumerate(lines[:2]):
                d.text((220, y + j * 58), ln, font=_font(54), fill=WHITE)
            _chip(d, (W - 130 - 300, y - 4), v, VCOLOR[v], size=40)
            y += pitch
        y += 10
        # kapanis cumlesi: footer'a (H-62) binmesin; sigmazsa punto kucult
        for pt, lh in ((44, 58), (40, 52), (36, 46)):
            ls = _wrap(d, cur["en"], _font(pt), maxw)
            if y + len(ls) * lh <= H - 90:
                break
        for ln in ls:
            d.text((130, y), ln, font=_font(pt), fill=MUTED)
            y += lh
    elif kind == "outro":
        y = 330
        for ln in _wrap(d, cur["en"], _font(86, True), maxw):
            d.text((W // 2, y), ln, font=_font(86, True), fill=WHITE, anchor="mm")
            y += 112
    else:
        raise ValueError(f"bilinmeyen sahne turu: {kind}")
    return img


def render_thumbnail(script, out_path, size=(1280, 720), line2=None):
    """YouTube kucuk resmi (1280x720, <2 MB). Hicbir KARAR gostermez; seri adi + '4 claims, scored' + uc rozet.
    Yuklemek icin YouTube Studio > video > Kucuk resim (otomatik yuklenmez)."""
    from PIL import Image, ImageDraw
    tw, th = size
    img = Image.new("RGB", size, BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(th):
        f = y / (th - 1)
        d.line([(0, y), (tw, y)], fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * f) for i in range(3)))
    n = sum(1 for s_ in script["scenes"] if s_.get("kind") == "claim")
    line2 = line2 or f"{n} AI CLAIMS, SCORED"
    # baslik: genislige sigana kadar kucult
    pt = 220
    while pt > 60 and d.textlength("HYPE OR REAL?", font=_font(pt, True)) > tw - 140:
        pt -= 6
    d.text((tw // 2, int(th * 0.30)), "HYPE OR REAL?", font=_font(pt, True), fill=ACCENT, anchor="mm")
    pt2 = 96
    while pt2 > 40 and d.textlength(line2, font=_font(pt2, True)) > tw - 160:
        pt2 -= 4
    d.text((tw // 2, int(th * 0.55)), line2, font=_font(pt2, True), fill=WHITE, anchor="mm")
    # uc rozet, ortali
    size_c = 54
    f = _font(size_c, True)
    widths = [d.textlength(v, font=f) + 44 for v in VERDICTS]
    gap = 36
    x = (tw - (sum(widths) + gap * (len(VERDICTS) - 1))) / 2
    y = int(th * 0.72)
    for v, w in zip(VERDICTS, widths):
        d.rounded_rectangle([x, y, x + w, y + size_c + 30], radius=(size_c + 30) // 2, fill=VCOLOR[v])
        d.text((x + 22, y + 13), v, font=f, fill=(15, 10, 25))
        x += w + gap
    d.text((tw // 2, th - 38), "Aura - an AI. Sources on screen.", font=_font(30), fill=MUTED, anchor="mm")
    img.save(out_path, "PNG", optimize=True)
    if os.path.getsize(out_path) > 1_900_000:      # YouTube siniri 2 MB
        out_path = os.path.splitext(out_path)[0] + ".jpg"
        img.save(out_path, "JPEG", quality=92)
    return out_path


# ------------------------------------------------------------------ ffmpeg / ses
def _run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg hatasi:\n" + (p.stderr[-1800:] if p.stderr else "?"))
    return p


def _duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
                       capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def voice_mesh_tts(url, key, speaker="aura", timeout=300):
    """Gercek ses: Voice Mesh /tts. (httpx, aura_studio ile ayni uc). Anahtar KODA GOMULU DEGIL."""
    def fn(text, out_wav):
        import httpx
        r = httpx.post(f"{url}/tts", headers={"X-Voice-Key": key}, json={"text": text, "speaker": speaker}, timeout=timeout)
        r.raise_for_status()
        with open(out_wav, "wb") as f:
            f.write(r.content)
        return out_wav
    return fn


def fake_tts(text, out_wav):
    """TEST/ONIZLEME: kelime sayisina gore sure, sessiz ses (gercek ses degil)."""
    dur = max(1.0, len(text.split()) / WORDS_PER_SEC)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", "-t", f"{dur:.3f}", out_wav])
    return out_wav


def make_longform(script, out_mp4, tts_fn, work_dir, status=None):
    """Tam uretim. status(msg) opsiyonel ilerleme bildirimi. Doner: {mp4, tr_srt, en_srt, description, scene_starts, duration}."""
    os.makedirs(work_dir, exist_ok=True)
    say = status or (lambda m: None)
    probs = [c for c in check_script(script) if c[0] is False]
    if probs:
        raise ValueError("Script kurallari: " + "; ".join(f"{l} ({d})" for _, l, d in probs))

    scenes = script["scenes"]
    # 1) ses (sahne basina)
    audios, durs = [], []
    for i, sc in enumerate(scenes):
        say(f"ses {i + 1}/{len(scenes)}")
        text = " ".join(s["en"] for s in _scene_sents(sc))
        wav = os.path.join(work_dir, f"scene{i:02d}.wav")
        tts_fn(text, wav)
        audios.append(wav)
        durs.append(_duration(wav) + PAD_SEC)
    total = sum(durs)
    starts, t = [], 0.0
    for d_ in durs:
        starts.append(t)
        t += d_

    # 2) kartlar + sahne videolari
    seg_paths = []
    en_tl, tr_tl = [], []
    for i, sc in enumerate(scenes):
        say(f"gorsel {i + 1}/{len(scenes)}")
        sents = _scene_sents(sc)
        w = [max(len(s["en"]), 1) for s in sents]
        wsum = sum(w)
        pure = durs[i] - PAD_SEC
        lst = []
        t0 = starts[i]
        for j, s in enumerate(sents):
            dj = pure * w[j] / wsum + (PAD_SEC if j == len(sents) - 1 else 0.0)
            img_path = os.path.join(work_dir, f"s{i:02d}_{j:02d}.png")
            render_card(script, sc, j, (t0 + dj / 2) / total).save(img_path)
            lst.append((img_path, dj))
            en_tl.append((s["en"], t0, dj - (PAD_SEC if j == len(sents) - 1 else 0.0)))
            tr_tl.append((s["tr"], t0, dj - (PAD_SEC if j == len(sents) - 1 else 0.0)))
            t0 += dj
        lst_file = os.path.join(work_dir, f"scene{i:02d}.txt")
        with open(lst_file, "w", encoding="utf-8") as f:
            for p_, dj in lst:
                f.write(f"file '{os.path.basename(p_)}'\nduration {dj:.3f}\n")
            f.write(f"file '{os.path.basename(lst[-1][0])}'\n")
        seg = os.path.join(work_dir, f"scene{i:02d}.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst_file, "-i", audios[i],
              "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-af", f"apad=pad_dur={PAD_SEC}", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-t", f"{durs[i]:.3f}", seg])
        seg_paths.append(seg)

    # 3) birlestir
    say("birlestirme")
    cl = os.path.join(work_dir, "all.txt")
    with open(cl, "w", encoding="utf-8") as f:
        for p_ in seg_paths:
            f.write(f"file '{os.path.basename(p_)}'\n")
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", cl, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_mp4])

    base = os.path.splitext(out_mp4)[0]
    build_srt(tr_tl, base + "_tr.srt")
    build_srt(en_tl, base + "_en.srt")
    ch = chapters(script, starts)
    desc = describe(script, ch)
    with open(base + "_description.txt", "w", encoding="utf-8") as f:
        f.write(desc)
    return {"mp4": out_mp4, "tr_srt": base + "_tr.srt", "en_srt": base + "_en.srt", "description": base + "_description.txt",
            "scene_starts": starts, "duration": total, "chapters": ch}


def describe(script, ch):
    parts = [script.get("description", "").strip(), "", "CHAPTERS", *ch, ""]
    links = script.get("links", [])
    if links:
        parts += ["SOURCES"] + [f"- {l}" for l in links] + [""]
    parts += ["I'm Aura, an AI. Every verdict here is my editorial judgment of the evidence shown on screen.", script.get("hashtags", "#AuraAI #HypeOrReal #AINews")]
    return "\n".join(parts)


def preview(script, out_dir):
    """Ses olmadan: sahne basina ilk ve (varsa) son cumle kareleri."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, sc in enumerate(script["scenes"]):
        sents = _scene_sents(sc)
        for j in sorted({0, len(sents) - 1}):
            p = os.path.join(out_dir, f"scene{i:02d}_{j:02d}_{sc['kind']}.png")
            render_card(script, sc, j, (i + 1) / len(script["scenes"])).save(p)
            paths.append(p)
    return paths


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", help="cikti mp4")
    ap.add_argument("--preview", help="ses olmadan kare onizlemesi klasoru")
    ap.add_argument("--check", action="store_true", help="sadece kural kontrolu")
    ap.add_argument("--thumbnail", help="YouTube kucuk resmi (1280x720 PNG) yolu")
    a = ap.parse_args()
    script = json.load(open(a.script, encoding="utf-8"))
    if a.thumbnail:
        print(render_thumbnail(script, a.thumbnail))
        return
    if a.check or not (a.out or a.preview):
        for ok, label, detail in check_script(script):
            print({True: "[OK] ", False: "[XX] ", None: "[..] "}[ok] + label + (f" - {detail}" if detail else ""))
        return
    if a.preview:
        print("\n".join(preview(script, a.preview)))
        return
    key = os.getenv("AURA_VOICE_KEY", "").strip()
    if not key:
        sys.exit("AURA_VOICE_KEY ortam degiskeni yok (Voice Mesh anahtari). Panelden calistir ya da set et.")
    url = (os.getenv("AURA_VOICE_URL") or "http://127.0.0.1:8123").rstrip("/")
    r = make_longform(script, a.out, voice_mesh_tts(url, key), os.path.join(HERE, "_video_work", "longform"), status=print)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
