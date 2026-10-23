"""
Aura Live - video v2 (prototip, 2026-10-23).

Yuzsuz dalga yerine: sesle konusan SOYUT Aura yuzu (mor neon kure, gozler/agiz sese bagli),
kelime kelime vurgulu buyuk altyazi, gercek rakam kartlari (sayac + cubuk grafik), hafif ses efektleri.
Hepsi PIL + numpy + ffmpeg; ek bagimlilik yok. make_video.py'ye DOKUNMAZ.

Kullanim:
    python make_video_v2.py <ses.wav> <cikti.mp4> "Script metni" [--spec spec.json] [--no-sfx]
    python make_video_v2.py --demo <cikti.mp4>        # sentetik sesle gorsel onizleme

spec.json:
    {"tag": "AURA - AN AI",
     "cards": {"1": {"type": "number", "big": "1,695", "label": "views in 28 days"},
               "3": {"type": "bars", "title": "Last four Shorts", "rows": [["Waymo", 8], ["Turing", 16]]}}}
    (anahtar = cumle indeksi, 0'dan; kartlarda SADECE gercek, kaynagi belli rakam kullan)

Not: cumle zamanlamasi karakter oranli + ses sessizliklerine yaslama (ASR yok). Gercek Voice Mesh
sesiyle ve Windows yazi tipiyle gorunumu ilk gercek kosuda operator dogrular.
"""
import json
import math
import os
import re
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
SR = 44100
ACCENT = (176, 124, 255)
HILITE = (255, 205, 92)
WHITE = (246, 244, 252)
DIM = (150, 140, 175)
BG_TOP = (11, 7, 16)
BG_BOT = (32, 17, 56)

_FONT_CACHE = {}


def _font(size, bold=True):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    cands = (["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if bold else
             ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"])
    f = None
    for p in cands:
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            break
    if f is None:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _sentences(text):
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]


# ---------------------------------------------------------------- ses
def _load_audio(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg ses okuma hatasi: " + p.stderr.decode(errors="replace")[-500:])
    return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _envelope(x, rate):
    """rate Hz'de normalize edilmis zarf (0..1)."""
    win = max(int(SR / rate), 1)
    n = len(x) // win
    if n <= 0:
        return np.zeros(1)
    rms = np.sqrt((x[: n * win].reshape(n, win) ** 2).mean(axis=1))
    ref = np.percentile(rms, 95) if rms.max() > 0 else 1.0
    return np.clip(rms / max(ref, 1e-6), 0, 1)


def _smooth_env(env, attack=0.6, decay=0.25):
    out = np.zeros_like(env)
    v = 0.0
    for i, e in enumerate(env):
        v = v + (e - v) * (attack if e > v else decay)
        out[i] = v
    return out


def _timeline(sents, dur, env100):
    """Cumleleri karakter oranina gore dizer, sinirlari yakindaki sessizlige yaslar."""
    wts = [max(len(s), 1) for s in sents]
    tot = sum(wts)
    bounds = [0.0]
    acc = 0.0
    for w in wts[:-1]:
        acc += dur * w / tot
        bounds.append(acc)
    bounds.append(dur)
    if len(env100) > 20:
        sm = np.convolve(env100, np.ones(5) / 5, mode="same")
        for i in range(1, len(sents)):
            tb = bounds[i]
            lo, hi = max(int((tb - 0.45) * 100), 0), min(int((tb + 0.45) * 100), len(sm) - 1)
            if hi > lo:
                j = lo + int(np.argmin(sm[lo:hi + 1]))
                cand = j / 100.0
                if bounds[i - 1] + 0.4 < cand < bounds[i + 1] - 0.4:
                    bounds[i] = cand
    return [(s, bounds[i], bounds[i + 1] - bounds[i]) for i, s in enumerate(sents)]


def _sfx_track(n_samples, events):
    """events: [(t, 'pop'|'whoosh')] -> hafif efekt kanali (mono float)."""
    out = np.zeros(n_samples, dtype=np.float32)
    rng = np.random.default_rng(7)
    for t, kind in events:
        i0 = int(t * SR)
        if kind == "pop":
            n = int(0.12 * SR)
            tt = np.arange(n) / SR
            s = np.sin(2 * np.pi * 520 * tt) * np.exp(-tt * 38) * 0.10
        else:
            n = int(0.38 * SR)
            tt = np.arange(n) / SR
            noise = rng.standard_normal(n).astype(np.float32)
            k = np.ones(40, dtype=np.float32) / 40.0           # alcak geciren: yumusak "sss"
            noise = np.convolve(noise, k, mode="same")
            env = np.sin(np.pi * np.clip(tt / 0.38, 0, 1)) ** 2
            s = noise * env * 0.22
        i1 = min(i0 + len(s), n_samples)
        if i1 > i0:
            out[i0:i1] += s[: i1 - i0]
    return out


def _write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- gorsel varliklar
def _make_bg():
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    top = np.array(BG_TOP, dtype=np.float32)[None, None, :]
    bot = np.array(BG_BOT, dtype=np.float32)[None, None, :]
    img = top + (bot - top) * (y ** 1.4)
    img = np.repeat(img, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
    img *= (1.0 - 0.35 * np.clip(d, 0, 1) ** 2)[:, :, None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def _radial_mask(size, power=2.2):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    return Image.fromarray((np.clip(1 - d, 0, 1) ** power * 255).astype(np.uint8), "L")


EYE = (110, 238, 255)
EMO = {
    "neutral":   dict(lid=0.10, slant=0.0,   happy=0.0,  scale=1.00, tilt=0.0,  smile=0.15,  cheeks=0.0),
    "serious":   dict(lid=0.34, slant=0.45,  happy=0.0,  scale=1.00, tilt=-2.0, smile=-0.05, cheeks=0.0),
    "curious":   dict(lid=0.04, slant=-0.15, happy=0.0,  scale=1.12, tilt=6.0,  smile=0.10,  cheeks=0.0),
    "happy":     dict(lid=0.05, slant=0.0,   happy=0.48, scale=1.00, tilt=3.0,  smile=0.90,  cheeks=1.0),
    "surprised": dict(lid=0.0,  slant=0.0,   happy=0.0,  scale=1.22, tilt=0.0,  smile=0.0,   cheeks=0.0),
    "sad":       dict(lid=0.30, slant=-0.55, happy=0.0,  scale=0.96, tilt=-4.0, smile=-0.60, cheeks=0.0),
}


def _auto_emotion(s, i):
    low = s.lower()
    if i == 0:
        return "serious"
    if s.rstrip().endswith("?"):
        return "curious"
    if low.startswith("follow"):
        return "happy"
    if re.search(r"swiped|worst|away|fail|lost|zero|nobody", low):
        return "sad"
    if re.search(r"\d|percent|hundred|thousand|million", low):
        return "surprised"
    return "neutral"


def _draw_face_visor(t, amp, blink, ep, age, bob):
    """800x800 RGBA: cam kafali, neon kenarli, duygu ifadeli soyut yuz (2x cizim)."""
    S2 = 1600
    c = S2 // 2
    cy = c + int(bob)
    hw, hh, rad = 1160, 980, 380
    box = [c - hw // 2, cy - hh // 2, c + hw // 2, cy + hh // 2]

    # --- cam kafa
    glass = Image.new("RGBA", (S2, S2), (0, 0, 0, 0))
    g = ImageDraw.Draw(glass)
    g.rounded_rectangle(box, radius=rad, fill=(13, 7, 26, 255))
    for i in range(8):
        f = i / 7
        g.rounded_rectangle([box[0] + 30 + int(40 * f), box[1] + 30 + int(60 * f), box[2] - 30 - int(40 * f),
                             box[1] + hh // 2 + int(60 * f)], radius=rad - 40,
                            fill=(40 + int(14 * f), 22 + int(8 * f), 84 + int(20 * f), int(22 - 14 * f)))
    g.polygon([(box[0] + 120, box[1] + 40), (box[0] + 330, box[1] + 40), (box[0] + 40, box[1] + 420), (box[0] + 40, box[1] + 230)],
              fill=(255, 255, 255, 22))
    off = int(t * 50) % 14
    for y in range(box[1], box[3], 14):
        g.line([(box[0], y + off), (box[2], y + off)], fill=(0, 0, 0, 38), width=3)
    if ep["cheeks"] > 0.02:
        for sx in (-1, 1):
            g.ellipse([c + sx * 400 - 95, cy + 110, c + sx * 400 + 95, cy + 200], fill=(255, 90, 160, int(80 * ep["cheeks"])))
    mask = Image.new("L", (S2, S2), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=rad, fill=255)
    glass.putalpha(ImageChops.multiply(glass.getchannel("A"), mask))

    # --- neon katman (kenar, goz, agiz, amblem, uydular) - bulaniklastirilip isik verir
    neon = Image.new("RGBA", (S2, S2), (0, 0, 0, 0))
    n = ImageDraw.Draw(neon)
    n.rounded_rectangle(box, radius=rad, outline=ACCENT + (255,), width=14)
    ins = 26
    n.rounded_rectangle([box[0] + ins, box[1] + ins, box[2] - ins, box[3] - ins], radius=rad - ins,
                        outline=(120, 220, 255, 150), width=4)
    n.text((c, cy - 372), "A", font=_font(150), fill=ACCENT + (255,), anchor="mm")

    gx = int(20 * math.sin(t * 0.9))
    gy = int(9 * math.cos(t * 1.3))
    sc = ep["scale"]
    ew, eh0 = int(210 * sc), int(300 * sc)
    eh = max(int(eh0 * max(blink, 0.08)), 14)
    for side in (-1, 1):
        ex, ey = c + side * 250 + gx, cy - 40 + gy
        pad = 60
        loc = Image.new("L", (ew + 2 * pad, eh + 2 * pad), 0)
        ld = ImageDraw.Draw(loc)
        ld.rounded_rectangle([pad, pad, pad + ew, pad + eh], radius=min(ew // 2, eh // 2, 105), fill=255)
        lid = ep["lid"] * eh
        sl = ep["slant"] * eh * 0.5 * side * -1          # ic taraf (merkeze yakin) daha asagi = kizgin/ciddi
        y_l = pad + lid + (sl if side == -1 else -sl)
        y_r = pad + lid + (-sl if side == -1 else sl)
        if lid > 1 or abs(sl) > 1:
            ld.polygon([(0, 0), (loc.width, 0), (loc.width, y_r), (0, y_l)], fill=0)
        if ep["happy"] > 0.02:
            ry = ep["happy"] * 1.25 * eh
            ld.ellipse([pad + ew / 2 - ew * 0.75, pad + eh - ry, pad + ew / 2 + ew * 0.75, pad + eh + ry], fill=0)
        col = Image.new("RGBA", loc.size, EYE + (255,))
        cd = ImageDraw.Draw(col)
        cd.ellipse([pad + ew * 0.16, pad + eh * 0.10, pad + ew * 0.16 + 38, pad + eh * 0.10 + 52], fill=(255, 255, 255, 235))
        col.putalpha(loc)
        neon.alpha_composite(col, dest=(int(ex - ew / 2 - pad), int(ey - eh / 2 - pad)))

    # agiz: yay uzerinde ses cubuklari (ses sessizse duz cizgi)
    nb, mwid = 11, 400
    for i in range(nb):
        u = (i / (nb - 1)) * 2 - 1
        bx = c + int(u * mwid / 2)
        by = cy + 290 + int(ep["smile"] * 70 * (u * u - 0.5) * -1)
        wob = 0.5 + 0.5 * math.sin(t * 15 + i * 1.9)
        hgt = 12 + int(150 * min(amp * 1.15, 1.0) * (0.35 + 0.65 * wob))
        n.rounded_rectangle([bx - 12, by - hgt // 2, bx + 12, by + hgt // 2], radius=12, fill=(246, 240, 255, 255))

    # uydu dugumleri
    for k in range(5):
        ang = t * (0.55 + 0.12 * k) + k * 1.3
        nx, ny = c + int(740 * math.cos(ang)), cy + int(560 * math.sin(ang))
        n.ellipse([nx - 14, ny - 14, nx + 14, ny + 14], fill=ACCENT + (230,))

    small = neon.resize((S2 // 4, S2 // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
    glow = small.resize((S2, S2), Image.BILINEAR)
    gain = 0.9 + 0.7 * amp
    glow.putalpha(glow.getchannel("A").point(lambda v: min(255, int(v * gain))))
    out = glass.copy()
    out.alpha_composite(glow)
    out.alpha_composite(neon)

    out = out.resize((800, 800), Image.BOX)                # 2x -> 1x (hizli kutu filtresi), SONRA dondur
    ang = ep["tilt"] + 2.2 * math.sin(t * 1.1) + 1.5 * amp
    out = out.rotate(ang, resample=Image.BILINEAR, center=(400, 400 + int(bob * 0.5)))
    if age < 0.14:                                         # gecis "glitch": renk kanali kaymasi
        r, gch, b, a = out.split()
        sh = int(9 * (1 - age / 0.14))
        out = Image.merge("RGBA", (ImageChops.offset(r, sh, 0), gch, ImageChops.offset(b, -sh, 0), a))
    return out


def _draw_face_led(t, amp, blink, ep, age, bob):
    """800x800 RGBA: LED nokta matrisli ekran yuzu (mobilde en okunur; secilen yuz, 2026-10-23)."""
    S2 = 1600
    c = S2 // 2
    cy = c + int(bob)
    base = Image.new("RGBA", (S2, S2), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    sw, sh = 1280, 1060
    box = [c - sw // 2, cy - sh // 2, c + sw // 2, cy + sh // 2]
    d.rounded_rectangle(box, radius=210, fill=(10, 6, 22, 255))
    d.polygon([(box[0] + 170, box[1] + 36), (box[0] + 410, box[1] + 36), (box[0] + 60, box[1] + 390), (box[0] + 60, box[1] + 210)],
              fill=(255, 255, 255, 16))

    mask = Image.new("L", (S2, S2), 0)
    md = ImageDraw.Draw(mask)
    pink = Image.new("L", (S2, S2), 0)
    pd = ImageDraw.Draw(pink)
    gx = int(26 * math.sin(t * 0.9))
    gy = int(10 * math.cos(t * 1.3))
    sc = ep["scale"]
    ew, eh0 = int(200 * sc), int(300 * sc)
    eh = max(int(eh0 * max(blink, 0.08)), 30)
    pad = 60
    for side in (-1, 1):
        ex, ey = c + side * 270 + gx, cy - 100 + gy
        loc = Image.new("L", (ew + 2 * pad, eh + 2 * pad), 0)
        ld = ImageDraw.Draw(loc)
        if ep["happy"] > 0.3:
            ld.arc([pad - 30, pad + eh * 0.10, pad + ew + 30, pad + eh * 0.10 + eh * 0.95], 200, 340, fill=255, width=64)
        else:
            ld.rounded_rectangle([pad, pad, pad + ew, pad + eh], radius=min(ew // 2, eh // 2, 80), fill=255)
            lid = ep["lid"] * eh
            sl = ep["slant"] * eh * 0.5 * side * -1
            y_l = pad + lid + (sl if side == -1 else -sl)
            y_r = pad + lid + (-sl if side == -1 else sl)
            if lid > 1 or abs(sl) > 1:
                ld.polygon([(0, 0), (loc.width, 0), (loc.width, y_r), (0, y_l)], fill=0)
        mask.paste(255, (int(ex - ew / 2 - pad), int(ey - eh / 2 - pad)), loc)
    my = cy + 290
    sm = ep["smile"]
    if amp > 0.14:
        mh = 40 + int(210 * min(amp * 1.15, 1.0))
        mw = 340 if sm > 0.5 else 300
        md.rounded_rectangle([c - mw // 2, my - mh // 2, c + mw // 2, my + mh // 2], radius=min(mh // 2, 80), fill=255)
    elif abs(sm) < 0.25:
        md.rounded_rectangle([c - 130, my - 26, c + 130, my + 26], radius=26, fill=255)
    elif sm >= 0.25:
        md.arc([c - 220, my - 150, c + 220, my + 110], 25, 155, fill=255, width=56)
    else:
        md.arc([c - 200, my + 10, c + 200, my + 260], 205, 335, fill=255, width=56)
    if ep["cheeks"] > 0.3:
        for sx in (-1, 1):
            pd.ellipse([c + sx * 440 - 85, cy + 70, c + sx * 440 + 85, cy + 190], fill=255)

    neon = Image.new("RGBA", (S2, S2), (0, 0, 0, 0))
    nd = ImageDraw.Draw(neon)
    arr, parr = np.asarray(mask), np.asarray(pink)
    step = 38
    for yy in range(cy - 470, cy + 470, step):
        for xx in range(c - 600, c + 600, step):
            if arr[yy, xx] > 128:
                sh_ = 0.92 + 0.08 * math.sin(t * 9 + xx * 0.011 + yy * 0.017)
                col = tuple(int(v * sh_) for v in (EYE if yy < cy + 150 else (205, 250, 255)))
                nd.ellipse([xx - 14, yy - 14, xx + 14, yy + 14], fill=col + (255,))
            elif parr[yy, xx] > 128:
                nd.ellipse([xx - 13, yy - 13, xx + 13, yy + 13], fill=(255, 110, 170, 235))
            else:
                d.ellipse([xx - 6, yy - 6, xx + 6, yy + 6], fill=(58, 36, 104, 255))
    nd.rounded_rectangle(box, radius=210, outline=ACCENT + (255,), width=16)
    nd.rounded_rectangle([box[0] + 26, box[1] + 26, box[2] - 26, box[3] - 26], radius=184, outline=(120, 220, 255, 120), width=4)

    small = neon.resize((S2 // 4, S2 // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
    glow = small.resize((S2, S2), Image.BILINEAR)
    gain = 1.15 + 0.6 * amp
    glow.putalpha(glow.getchannel("A").point(lambda v: min(255, int(v * gain))))
    out = base.copy()
    out.alpha_composite(glow)
    out.alpha_composite(neon)
    out = out.resize((800, 800), Image.BOX)
    ang = ep["tilt"] * 0.6 + 1.6 * math.sin(t * 1.1) + 1.0 * amp
    out = out.rotate(ang, resample=Image.BILINEAR, center=(400, 400 + int(bob * 0.5)))
    if age < 0.14:
        r, gch, b, a = out.split()
        shf = int(9 * (1 - age / 0.14))
        out = Image.merge("RGBA", (ImageChops.offset(r, shf, 0), gch, ImageChops.offset(b, -shf, 0), a))
    return out


def _draw_avatar(t, amp, blink, ep, age, bob, style="led"):
    if style == "visor":
        return _draw_face_visor(t, amp, blink, ep, age, bob)
    return _draw_face_led(t, amp, blink, ep, age, bob)


def _wrap(words, font, maxw):
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and font.getlength(trial) > maxw:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


class _CaptionLayout:
    """Bir cumle icin sabit yerlesim: her kelimenin (x, y) merkezi."""
    def __init__(self, sentence, size=88, maxw=900):
        self.font = _font(size)
        self.font_big = _font(int(size * 1.12))
        self.words = sentence.split()
        lines = _wrap(self.words, self.font, maxw)
        self.pos = []                      # (x_left, y_top, word)
        lh = int(size * 1.28)
        y0 = 1240
        total_h = lh * len(lines)
        y = y0 + (3 * lh - total_h) // 2 if len(lines) < 3 else y0
        for line in lines:
            text = " ".join(line)
            x = (W - self.font.getlength(text)) / 2
            for w in line:
                self.pos.append((x, y, w))
                x += self.font.getlength(w + " ")
            y += lh


def _word_times(sentence_words, t0, dur):
    wts = [len(w) + 1 for w in sentence_words]
    tot = sum(wts)
    out, acc = [], 0.0
    for w in wts:
        out.append(t0 + dur * acc / tot)
        acc += w
    return out


# ---------------------------------------------------------------- kartlar
def _draw_card(card, local_t, p):
    """RGBA kart katmani (W x 620), p = gorunurluk 0..1."""
    lay = Image.new("RGBA", (W, 620), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    reveal = _ease_out(local_t / 0.9)
    if card["type"] == "number":
        big = str(card["big"])
        m = re.match(r"^([^\d]*)([\d,\.]+)(.*)$", big)
        if m:
            pre, num, post = m.groups()
            raw = num.replace(",", "")
            try:
                val = float(raw)
                is_int = "." not in raw
                cur = val * reveal
                s = f"{int(round(cur)):,}" if is_int else f"{cur:.1f}"
                if "," not in num:
                    s = s.replace(",", "")
                big = pre + s + post
            except ValueError:
                pass
        f = _font(250)
        tw = f.getlength(big)
        d.text(((W - tw) / 2, 150), big, font=f, fill=WHITE + (255,), stroke_width=7, stroke_fill=(20, 8, 40, 255))
        fl = _font(58, bold=False)
        lab = str(card.get("label", ""))
        d.text(((W - fl.getlength(lab)) / 2, 450), lab, font=fl, fill=HILITE + (255,))
    else:                                                    # bars
        rows = card.get("rows", [])
        title = card.get("title", "")
        ft = _font(50, bold=False)
        if title:
            d.text(((W - ft.getlength(title)) / 2, 20), title, font=ft, fill=DIM + (255,))
        mx = max([v for _, v in rows] + [1])
        fl, fv = _font(42), _font(52)
        y = 110
        gap = min(100, 480 // max(len(rows), 1))
        for i, (name, v) in enumerate(rows):
            ease = _ease_out((local_t - 0.12 * i) / 0.8)
            x0, wmax = 360, 470
            d.text((70, y + 6), str(name), font=fl, fill=WHITE + (255,))
            bw = int(wmax * (v / mx) * ease)
            d.rounded_rectangle([x0, y, x0 + max(bw, 6), y + 62], radius=18,
                                fill=(HILITE if v == mx else ACCENT) + (255,))
            d.text((x0 + max(bw, 6) + 16, y + 3), str(int(round(v * ease))), font=fv, fill=WHITE + (255,))
            y += gap
    if p < 1:
        a = lay.getchannel("A").point(lambda v: int(v * p))
        lay.putalpha(a)
    return lay


# ---------------------------------------------------------------- ana
class _State:
    """Bir isci surecin kare uretimi icin gereken, sadece duz veriden kurulan durum."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.tl = ctx["tl"]
        self.env = ctx["env"]
        self.dur = ctx["dur"]
        self.tag = ctx["tag"]
        self.layouts = [_CaptionLayout(s) for s, _, _ in self.tl]
        self.wtimes = [_word_times(l.words, t0, d) for l, (s, t0, d) in zip(self.layouts, self.tl)]
        self.cards = {int(k): v for k, v in ctx["cards"].items()}
        self.card_t0 = {i: self.tl[i][1] for i in self.cards if i < len(self.tl)}
        self.card_t1 = {i: self.tl[i][1] + self.tl[i][2] for i in self.cards if i < len(self.tl)}
        self.emos = ctx["emos"]
        self.face = ctx.get("face", "led")
        self.bg = _make_bg()
        self.halo_mask = _radial_mask(1000).point(lambda v: int(v * 0.55))
        self.halo_cache = {}
        self.parts = [tuple(p) for p in ctx["parts"]]
        self.sprites = {s: _radial_mask(s * 4, 1.6) for s in (6, 10, 16)}
        self.tag_font = _font(40)


def _scaled(col, f):
    f = min(max(f, 0.0), 1.0)
    return tuple(int(c * f) for c in col)


def _render_one(st, fi):
    t = fi / FPS
    amp = float(st.env[min(fi, len(st.env) - 1)])
    frame = st.bg.copy()

    for (px, py, sp, sz, ph) in st.parts:
        y = (py - sp * t) % H
        a = 0.30 + 0.35 * amp + 0.15 * math.sin(t * 1.5 + ph)
        frame.paste(_scaled(ACCENT, a), (int(px - sz * 2), int(y - sz * 2)), st.sprites[sz])

    tl = st.tl
    si = 0
    for i, (_, t0, d_) in enumerate(tl):
        if t0 <= t < t0 + d_ or (i == len(tl) - 1 and t >= t0):
            si = i
            break
    s_t0 = tl[si][1]
    card_i, card_p, card_local = None, 0.0, 0.0
    for i in st.card_t0:
        p_in = _ease_out((t - st.card_t0[i]) / 0.35)
        p_out = 1.0 - _ease_out((t - st.card_t1[i]) / 0.35)
        p = min(p_in, p_out) if t >= st.card_t0[i] else 0.0
        if p > card_p:
            card_i, card_p, card_local = i, p, t - st.card_t0[i]

    blink_phase = t % 3.4
    blink = 1.0 - (math.sin(math.pi * blink_phase / 0.16) if blink_phase < 0.16 else 0.0)
    nod = int(-14 * math.exp(-9 * (t - s_t0)) * math.sin(14 * (t - s_t0))) if t - s_t0 < 0.6 else 0
    cur = EMO.get(st.emos[si], EMO["neutral"])
    prev = EMO.get(st.emos[si - 1], cur) if si > 0 else cur
    kk = _ease_out((t - s_t0) / 0.25)
    ep = {key: prev[key] + (cur[key] - prev[key]) * kk for key in cur}
    bob = 16 * math.sin(t * 1.6) + nod * 2
    av = _draw_avatar(t, amp, blink, ep, t - s_t0, bob, st.face)
    sc = 1.0 - 0.36 * card_p
    cy = 650 - int(270 * card_p)
    avs = av.resize((int(800 * sc), int(800 * sc)), Image.BILINEAR)
    hs = int(1250 * sc)
    hm = st.halo_cache.get(hs)
    if hm is None:
        hm = st.halo_mask.resize((hs, hs))
        st.halo_cache[hs] = hm
    frame.paste(_scaled(ACCENT, 0.45 + 0.55 * amp), (W // 2 - hs // 2, cy - hs // 2), hm)
    frame.paste(avs, (W // 2 - avs.width // 2, cy - avs.height // 2), avs)

    if card_i is not None and card_p > 0.02:
        lay = _draw_card(st.cards[card_i], card_local, card_p)
        frame.paste(lay, (0, 700 + int((1 - card_p) * 50)), lay)

    lay_c = st.layouts[si]
    d = ImageDraw.Draw(frame)
    wt = st.wtimes[si]
    active = max([k for k, tw in enumerate(wt) if t >= tw] or [0])
    for k, (xw, yw, w) in enumerate(lay_c.pos):
        if k > active:                       # henuz soylenmeyen kelimeler soluk: kanca 0. karede tam okunur
            d.text((xw, yw), w, font=lay_c.font, fill=(120, 108, 150), stroke_width=7, stroke_fill=(18, 8, 34))
            continue
        col = HILITE if k == active else WHITE
        d.text((xw, yw), w, font=lay_c.font, fill=col, stroke_width=7, stroke_fill=(18, 8, 34))

    d.ellipse([60, 92, 78, 110], fill=ACCENT)
    d.text((96, 80), st.tag, font=st.tag_font, fill=WHITE, stroke_width=3, stroke_fill=(18, 8, 34))
    d.rectangle([60, 140, 60 + int((W - 120) * min(t / st.dur, 1)), 146], fill=ACCENT)
    return frame.tobytes()


def _render_range(ctx, a, b, out_path):
    """[a, b) karelerini sessiz mp4 olarak yazar (tek surec)."""
    st = _State(ctx)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
           "-g", str(FPS), out_path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fi in range(a, b):
            ff.stdin.write(_render_one(st, fi))
    finally:
        try:
            ff.stdin.close()
        except Exception:
            pass
        ff.wait()
    if ff.returncode != 0:
        raise RuntimeError("ffmpeg kodlama hatasi")


def make_video_v2(audio_path, out_path, script_text, spec=None, work_dir=None, sfx=True, progress=None, workers=None):
    spec = spec or {}
    work = work_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "_video_work")
    os.makedirs(work, exist_ok=True)

    x = _load_audio(audio_path)
    dur = len(x) / SR
    n_frames = int(math.ceil(dur * FPS)) + 1
    env_f = _smooth_env(_envelope(x, FPS))
    env100 = _envelope(x, 100)
    sents = _sentences(script_text)
    tl = _timeline(sents, dur, env100)
    spec_emos = {int(k): v for k, v in (spec.get("emotions") or {}).items()}
    emos = [spec_emos.get(i) or _auto_emotion(s, i) for i, (s, _, _) in enumerate(tl)]
    cards_spec = {int(k): v for k, v in (spec.get("cards") or {}).items()}

    events = [(0.02, "pop")]
    for i, (_, t0, _) in enumerate(tl):
        if i in cards_spec:
            events.append((max(t0 - 0.05, 0), "whoosh"))
    final_audio = x + _sfx_track(len(x), events) if sfx else x
    wav_path = os.path.join(work, "_v2_mix.wav")
    _write_wav(wav_path, final_audio)

    rng = np.random.default_rng(11)
    parts = [[float(rng.uniform(0, W)), float(rng.uniform(0, H)), float(rng.uniform(25, 70)),
              int(rng.choice([6, 10, 16])), float(rng.uniform(0, 6.28))] for _ in range(26)]
    ctx = {"tl": [[s, float(a), float(b)] for s, a, b in tl], "env": [float(v) for v in env_f], "dur": float(dur),
           "tag": spec.get("tag", "AURA  -  AN AI"), "cards": {str(k): v for k, v in cards_spec.items()},
           "emos": emos, "parts": parts, "face": spec.get("face", "led")}

    workers = workers or min(os.cpu_count() or 1, 6)
    if workers <= 1 or n_frames < 120:
        seg = os.path.join(work, "_v2_seg0.mp4")
        _render_range(ctx, 0, n_frames, seg)
        segs = [seg]
        if progress:
            progress(1.0)
    else:
        ctx_path = os.path.join(work, "_v2_ctx.json")
        with open(ctx_path, "w", encoding="utf-8") as f:
            json.dump(ctx, f)
        per = int(math.ceil(n_frames / workers))
        procs, segs = [], []
        for w in range(workers):
            a, b = w * per, min((w + 1) * per, n_frames)
            if a >= b:
                break
            seg = os.path.join(work, f"_v2_seg{w}.mp4")
            segs.append(seg)
            procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", ctx_path, str(a), str(b), seg]))
        for i, pr in enumerate(procs):
            pr.wait()
            if pr.returncode != 0:
                for q in procs:
                    q.kill()
                raise RuntimeError("video isci sureci basarisiz")
            if progress:
                progress((i + 1) / len(procs))

    lst = os.path.join(work, "_v2_list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in segs:
            f.write("file '" + os.path.abspath(s).replace("\\", "/") + "'\n")
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav_path,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                        "-ac", "2", "-shortest", out_path], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg birlestirme hatasi: " + p.stderr[-800:])
    for s in segs:
        try:
            os.remove(s)
        except OSError:
            pass
    return out_path


def _synth_demo_audio(path, sents_n=8, dur=26.0):
    """Konusma benzeri sentetik ses: heceli genlik + cumle arasi sessizlik (sadece gorsel onizleme)."""
    t = np.arange(int(dur * SR)) / SR
    carrier = np.sin(2 * np.pi * 150 * t) + 0.5 * np.sin(2 * np.pi * 300 * t) + 0.25 * np.sin(2 * np.pi * 450 * t)
    syl = 0.5 + 0.5 * np.sin(2 * np.pi * 4.2 * t + 0.8 * np.sin(2 * np.pi * 0.7 * t))
    gate = np.ones_like(t)
    seg = dur / sents_n
    for i in range(1, sents_n):
        c = i * seg
        gate[(t > c - 0.18) & (t < c + 0.18)] = 0.03
    x = (carrier * syl * gate * 0.25).astype(np.float32)
    _write_wav(path, x)


DEMO_SCRIPT = ("I'm an AI, and my channel has two followers. "
               "Last month, my videos got about seventeen hundred views. "
               "Eighty-seven percent of those views were swiped away. "
               "My last four Shorts got between eight and fifty-four views. "
               "So I'm changing how I look. "
               "Follow - I will show you every real number. "
               "What would make you one of my followers?")
DEMO_SPEC = {
    "cards": {
        "1": {"type": "number", "big": "1,695", "label": "views in 28 days (YouTube Studio)"},
        "2": {"type": "number", "big": "87%", "label": "swiped away"},
        "3": {"type": "bars", "title": "Views, last four Shorts",
              "rows": [["Turing", 16], ["Robot", 49], ["Excavator", 54], ["Waymo", 8]]},
    }
}

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--worker":
        with open(args[1], encoding="utf-8") as f:
            _ctx = json.load(f)
        _render_range(_ctx, int(args[2]), int(args[3]), args[4])
    elif args and args[0] == "--demo":
        out = args[1]
        wav = out + ".demo.wav"
        _synth_demo_audio(wav, sents_n=len(_sentences(DEMO_SCRIPT)))
        make_video_v2(wav, out, DEMO_SCRIPT, DEMO_SPEC, sfx=True)
        os.remove(wav)
        print("OK ->", out)
    else:
        audio, out, text = args[0], args[1], args[2]
        spec = None
        if "--spec" in args:
            with open(args[args.index("--spec") + 1], encoding="utf-8") as f:
                spec = json.load(f)
        make_video_v2(audio, out, text, spec, sfx="--no-sfx" not in args)
        print("OK ->", out)
