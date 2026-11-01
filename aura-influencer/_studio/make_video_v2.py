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
import scene3d
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
    """events: [(t, 'pop'|'whoosh'|'thud'[, kazanc])] -> hafif efekt kanali (mono float)."""
    out = np.zeros(n_samples, dtype=np.float32)
    rng = np.random.default_rng(7)
    for ev in events:
        t, kind = ev[0], ev[1]
        gain = ev[2] if len(ev) > 2 else 1.0
        i0 = int(t * SR)
        if kind == "pop":
            n = int(0.12 * SR)
            tt = np.arange(n) / SR
            s = np.sin(2 * np.pi * 520 * tt) * np.exp(-tt * 38) * 0.10
        elif kind == "thud":                                     # ayak sesi: alcak vurus + kisa tik
            n = int(0.22 * SR)
            tt = np.arange(n) / SR
            s = (np.sin(2 * np.pi * (95 - 40 * tt) * tt) * np.exp(-tt * 22) * 0.9
                 + rng.standard_normal(n).astype(np.float32) * np.exp(-tt * 140) * 0.25)
        else:
            n = int(0.38 * SR)
            tt = np.arange(n) / SR
            noise = rng.standard_normal(n).astype(np.float32)
            k = np.ones(40, dtype=np.float32) / 40.0           # alcak geciren: yumusak "sss"
            noise = np.convolve(noise, k, mode="same")
            env = np.sin(np.pi * np.clip(tt / 0.38, 0, 1)) ** 2
            s = noise * env * 0.22
        s = s * gain
        i1 = min(i0 + len(s), n_samples)
        if i1 > i0:
            out[i0:i1] += s[: i1 - i0]
    return out


def _music_track(n_samples, seed=3, level=0.035):
    """Kendi uretimimiz ambient muzik yatagi (telifsiz): yavas pad (a-minor) + seyrek pluck notalari."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / SR
    out = np.zeros(n_samples, dtype=np.float32)
    for f, a in ((110.0, 1.0), (164.81, 0.7), (220.0, 0.6), (261.63, 0.45), (329.63, 0.4)):
        for det in (-0.6, 0.0, 0.7):
            out += (a * 0.2 * np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 6.28))).astype(np.float32)
    out *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)).astype(np.float32)
    scale = [220.0, 261.63, 293.66, 329.63, 392.0, 440.0, 523.25]
    step = 0.5
    for k in range(int(n_samples / SR / step)):
        if rng.random() < 0.55:
            f = float(rng.choice(scale)) * (2.0 if rng.random() < 0.3 else 1.0)
            i0 = int(k * step * SR)
            nn = int(0.6 * SR)
            tt = np.arange(nn) / SR
            p = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 6.0) * 0.12
            i1 = min(i0 + nn, n_samples)
            if i1 > i0:
                out[i0:i1] += p[: i1 - i0].astype(np.float32)
    fade = np.minimum(1.0, np.minimum(t / 0.8, (n_samples / SR - t) / 0.8)).astype(np.float32)
    return out * fade * level


def _walk_step_times():
    """scene3d intro: ayak temas anlari (JS walkState ile ayni model: v = 1.78 (1-(t/3)^3), faz = 2pi*v/1.24)."""
    vmax, tw = 1.78, 3.0
    ts, ph, t, dt, nxt = [], 0.0, 0.0, 1 / 480.0, np.pi
    while t < tw:
        v = vmax * (1 - (t / tw) ** 3)
        ph += 2 * np.pi * v / 1.24 * dt
        t += dt
        if ph >= nxt:
            ts.append(t)
            nxt += np.pi
    return ts


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


def _draw_face_led(t, amp, blink, ep, age, bob, plate=True):
    """800x800 RGBA: LED nokta matrisli ekran yuzu (mobilde en okunur; secilen yuz, 2026-10-23)."""
    S2 = 1600
    c = S2 // 2
    cy = c + int(bob)
    base = Image.new("RGBA", (S2, S2), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    sw, sh = 1280, 1060
    box = [c - sw // 2, cy - sh // 2, c + sw // 2, cy + sh // 2]
    if plate:
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
    if plate:
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


# ---------------------------------------------------------------- Aura Bot: govdeli karakter + kendi sahnemiz (face="bot")
# Havada suzulen robot: metal kafa (icinde LED ekran yuz), ince boyun, "A" gogus amblemi, kenetsiz suzulen eller,
# altta isik yayici + zemin halkalari. Arka planda kendi stüdyomuz: spot isiklar, zemin izgarasi, ses esitleyici duvari.
FW, FH = 900, 1000
STEEL_TOP = (84, 74, 124)
STEEL_BOT = (22, 16, 42)
_BOT_CACHE = {}


def _grad_fill(size, top, bot):
    arr = np.linspace(0, 1, size[1], dtype=np.float32)[:, None, None]
    t = np.array(top, np.float32)[None, None, :]
    b = np.array(bot, np.float32)[None, None, :]
    img = np.repeat(t + (b - t) * arr, size[0], axis=1)
    return Image.fromarray(img.astype(np.uint8), "RGB")


def _torso_hw(y, y0=548, y1=905, w=262, r=70):
    t = y - y0
    span = y1 - y0
    if t < 0 or t > span:
        return 0.0
    u = t / span
    hw = 90 + (w - 90) * (1 - u ** 1.9) ** 0.55
    if t < r:
        hw -= r - math.sqrt(max(r * r - (r - t) ** 2, 0))
    return max(hw, 0.0)


def _bot_static():
    """Sabit parcalar (kafa kabugu, boyun, govde, dikisler): bir kez 2x cizilir, kucultulup onbellege alinir."""
    if "s" in _BOT_CACHE:
        return _BOT_CACHE["s"]
    S = 2
    big = (FW * S, FH * S)
    im = Image.new("RGBA", big, (0, 0, 0, 0))
    grad = _grad_fill(big, STEEL_TOP, STEEL_BOT).convert("RGBA")

    def sc(pts):
        return [(int(x * S), int(y * S)) for x, y in pts]

    # govde
    outline = [(450 - _torso_hw(y), y) for y in range(548, 906, 3)] + [(450 + _torso_hw(y), y) for y in range(905, 547, -3)]
    m = Image.new("L", big, 0)
    ImageDraw.Draw(m).polygon(sc(outline), fill=255)
    im.paste(grad, (0, 0), m)
    d = ImageDraw.Draw(im)
    d.line(sc(outline + [outline[0]]), fill=ACCENT + (255,), width=5 * S, joint="curve")
    seam = (150, 120, 235, 120)
    d.line(sc([(450, 590), (450, 645)]), fill=seam, width=4 * S)
    d.line(sc([(450, 785), (450, 880)]), fill=seam, width=4 * S)
    for sg in (-1, 1):
        d.line(sc([(450 + sg * 175, 610), (450 + sg * 118, 870)]), fill=seam, width=4 * S)
    hw = _torso_hw(640)
    d.line(sc([(450 - hw + 20, 640), (450 + hw - 20, 640)]), fill=(150, 120, 235, 90), width=3 * S)
    # boyun
    d.rounded_rectangle([int(390 * S), int(500 * S), int(510 * S), int(566 * S)], radius=18 * S, fill=(30, 24, 56, 255),
                        outline=(120, 95, 200, 255), width=3 * S)
    for yy in (518, 534, 550):
        d.line(sc([(398, yy), (502, yy)]), fill=(90, 70, 150, 200), width=2 * S)
    # kulaklar
    for sg in (-1, 1):
        cx = 450 + sg * 262
        d.rounded_rectangle([int((cx - 30) * S), int(235 * S), int((cx + 30) * S), int(365 * S)], radius=28 * S,
                            fill=(40, 32, 72, 255), outline=(110, 220, 255, 255), width=4 * S)
    # kafa kabugu
    hm = Image.new("L", big, 0)
    ImageDraw.Draw(hm).rounded_rectangle([int(200 * S), int(80 * S), int(700 * S), int(520 * S)], radius=135 * S, fill=255)
    im.paste(grad, (0, 0), hm)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([int(200 * S), int(80 * S), int(700 * S), int(520 * S)], radius=135 * S, outline=ACCENT + (255,), width=6 * S)
    d.rounded_rectangle([int(222 * S), int(102 * S), int(678 * S), int(498 * S)], radius=115 * S, fill=(12, 8, 26, 255))
    shine = Image.new("RGBA", big, (0, 0, 0, 0))
    ImageDraw.Draw(shine).polygon(sc([(290, 92), (470, 92), (232, 250), (214, 200)]), fill=(255, 255, 255, 34))
    im.alpha_composite(shine)
    d = ImageDraw.Draw(im)
    # anten
    d.line(sc([(450, 82), (450, 44)]), fill=(150, 130, 210, 255), width=9 * S)
    out = im.resize((FW, FH), Image.LANCZOS)
    _BOT_CACHE["s"] = out
    return out


def _draw_bot(t, amp, blink, ep, age, bob):
    base = _bot_static().copy()
    bd = ImageDraw.Draw(base)
    neon = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    nd = ImageDraw.Draw(neon)
    pulse = 0.55 + 0.45 * amp
    # zemin halkalari + isik huzmesi + yayici
    for rx, ry, a in ((330, 40, 80), (240, 28, 120), (150, 18, 170)):
        nd.ellipse([450 - rx, 968 - ry, 450 + rx, 968 + ry], outline=ACCENT + (int(a * pulse),), width=5)
    nd.polygon([(380, 910), (520, 910), (650, 962), (250, 962)], fill=ACCENT + (int(42 * pulse),))
    nd.ellipse([360, 890, 540, 926], fill=(205, 170, 255, int(150 + 100 * amp)))
    # gogus amblemi
    nd.ellipse([388, 653, 512, 777], outline=(110, 238, 255, int(190 + 60 * amp)), width=6)
    ef = _font(86)
    nd.text((450 - ef.getlength("A") / 2, 668), "A", font=ef, fill=(246, 244, 252, int(200 + 55 * amp)))
    # anten topu
    ar = 13 + int(6 * amp)
    nd.ellipse([450 - ar, 40 - ar, 450 + ar, 40 + ar], fill=HILITE + (int(170 + 85 * amp),))
    # suzulen eller + enerji bagi
    raise_ = 30 * amp + 70 * ep["happy"]
    for sg in (-1, 1):
        hx = 450 + sg * 345 + 10 * math.sin(t * 1.3 + sg)
        hy = 700 + 16 * math.sin(t * 1.7 + sg * 1.4) - raise_
        nd.line([(450 + sg * 246, 612), (hx, hy)], fill=(110, 238, 255, 150), width=4)
        bd.ellipse([hx - 56, hy - 56, hx + 56, hy + 56], fill=(46, 38, 82, 255))
        bd.ellipse([hx - sg * 40 - 22, hy + 26 - 22, hx - sg * 40 + 22, hy + 26 + 22], fill=(46, 38, 82, 255))
        nd.ellipse([hx - 56, hy - 56, hx + 56, hy + 56], outline=ACCENT + (255,), width=5)
        nd.ellipse([hx - sg * 40 - 22, hy + 26 - 22, hx - sg * 40 + 22, hy + 26 + 22], outline=ACCENT + (255,), width=4)
    small = neon.resize((FW // 4, FH // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
    glow = small.resize((FW, FH), Image.BILINEAR)
    gain = 1.1 + 0.8 * amp
    glow.putalpha(glow.getchannel("A").point(lambda v: min(255, int(v * gain))))
    base.alpha_composite(glow)
    base.alpha_composite(neon)
    face = _draw_face_led(t, amp, blink, ep, age, bob * 0.4).resize((500, 500), Image.BILINEAR)
    base.alpha_composite(face, (200, 50))
    return base



# ---------------------------------------------------------------- Aura Robot: 3B render edilmis insansi robot (face="robot")
# Robot onceden three.js ile PBR malzeme/golge/yansimayla render edildi (_studio/robot3d, _studio/assets/aura_robot).
# Burada sadece PIL ile: poz sprite'lari (p0 sakin, p1 el kaldirir, p2 avuc acik) + vizor UV haritasina sesle konusan LED yuz basilir.
ROBOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "aura_robot")
RU0, RU1, RV0, RV1 = 0.15, 0.85, 0.24, 0.82      # vizor UV'sinde yuzun kapladigi bolge
RTW, RTH = 330, 275                              # yuz dokusu boyutu
_ROBOT = {}


def _robot_assets():
    if _ROBOT:
        return _ROBOT
    for k in ("p0", "p1", "p2"):
        base = Image.open(os.path.join(ROBOT_DIR, f"c_{k}.png")).convert("RGBA")
        uv = np.asarray(Image.open(os.path.join(ROBOT_DIR, f"c_{k}_uv.png")).convert("RGBA")).astype(np.float32)
        m = np.clip((uv[..., 2] - 128.0) / 127.0, 0, 1) * (uv[..., 3] >= 250)
        ys, xs = np.nonzero(m > 0.04)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        sub = uv[y0:y1, x0:x1]
        fx = (sub[..., 0] / 255.0 - RU0) / (RU1 - RU0)
        fy = 1.0 - (sub[..., 1] / 255.0 - RV0) / (RV1 - RV0)
        valid = (fx >= 0) & (fx <= 1) & (fy >= 0) & (fy <= 1)
        _ROBOT[k] = {
            "base": base, "bbox": (int(x0), int(y0), int(x1), int(y1)), "mask": m[y0:y1, x0:x1] * valid,
            "ix": np.clip(fx * (RTW - 1), 0, RTW - 1).astype(np.int32), "iy": np.clip(fy * (RTH - 1), 0, RTH - 1).astype(np.int32),
            "vmask": m[y0:y1, x0:x1],
        }
    h = _ROBOT["p0"]["base"].size[1]
    fade = np.ones((h, 1), np.float32)               # alt kisimda govde sahneye eriyip kaybolur (altyazilar okunsun)
    a0, a1 = int(h * 0.80), int(h * 0.97)
    fade[a0:a1, 0] = np.linspace(1, 0, a1 - a0)
    fade[a1:, 0] = 0
    _ROBOT["fade"] = fade
    return _ROBOT


def _draw_robot(t, amp, blink, ep, age, bob, w_pose):
    """w_pose: (w0, w1, w2) agirliklari (toplam 1). Donus: RGBA sprite (1080x1190)."""
    ra = _robot_assets()
    img = ra["p0"]["base"]
    ws = [max(float(x), 0.0) for x in w_pose]
    tot = sum(ws) or 1.0
    ws = [x / tot for x in ws]
    names = ("p0", "p1", "p2")
    base = Image.blend(img, ra["p1"]["base"], ws[1]) if ws[1] > 0.001 and ws[2] < 0.001 else None
    if base is None:
        base = img
        acc = ws[0]
        for nm, wv in zip(names[1:], ws[1:]):
            if wv > 0.001:
                acc += wv
                base = Image.blend(base, ra[nm]["base"], wv / acc)
    dom = names[int(np.argmax(ws))]
    pz = ra[dom]
    face = _draw_face_led(t, amp, blink, ep, age, 0, plate=False)
    face = face.crop((70, 125, 730, 675)).resize((RTW, RTH), Image.BOX)
    tex = np.asarray(face).astype(np.float32)
    em = tex[pz["iy"], pz["ix"]]
    a = em[..., 3:4] / 255.0
    rgb = em[..., :3] * a * pz["mask"][..., None]
    x0, y0, x1, y1 = pz["bbox"]
    reg = np.asarray(base.crop((x0, y0, x1, y1))).astype(np.float32)
    glow_img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(7))
    glow = np.asarray(glow_img).astype(np.float32) * pz["vmask"][..., None]
    reg[..., :3] = np.clip(reg[..., :3] + rgb * 1.15 + glow * 0.75, 0, 255)
    out = base.copy()
    out.paste(Image.fromarray(reg.astype(np.uint8), "RGBA"), (x0, y0))
    al = np.asarray(out.getchannel("A")).astype(np.float32) * ra["fade"]
    out.putalpha(Image.fromarray(al.astype(np.uint8), "L"))
    return out



def _draw_eq(t, amp):
    """Arka plandaki ses esitleyici duvari (sesle birlikte dalgalanir, cok silik)."""
    lay = Image.new("RGBA", (W, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    n, bw = 21, 34
    gap = (W - n * bw) / (n + 1)
    for i in range(n):
        ph = abs(math.sin(t * 2.6 + i * 0.9)) * 0.6 + abs(math.sin(t * 1.3 + i * 0.37)) * 0.4
        h = 40 + (150 + 520 * amp) * ph
        x = gap + i * (bw + gap)
        d.rounded_rectangle([x, 450 - h / 2, x + bw, 450 + h / 2], radius=14, fill=ACCENT + (46,))
    return lay


def _make_bg_stage():
    """Kendi sahnemiz: koyu stüdyo, iki spot isik, ufuk parlamasi, perspektifli zemin izgarasi."""
    img = _make_bg().convert("RGBA")
    horizon = 1190
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rectangle([0, horizon, W, H], fill=(8, 5, 18, 235))                      # zemin
    for k in range(-12, 13):                                                    # perspektif dikeyleri
        d.line([(W / 2 + k * 40, horizon), (W / 2 + k * 190, H)], fill=ACCENT + (58,), width=2)
    for j in range(1, 10):                                                      # yataylar
        y = horizon + (j / 9.0) ** 1.7 * (H - horizon)
        d.line([(0, y), (W, y)], fill=ACCENT + (46,), width=2)
    for y, a in ((horizon, 130), (horizon - 6, 70), (horizon + 6, 70)):         # ufuk cizgisi
        d.line([(0, y), (W, y)], fill=(170, 130, 255, a), width=3)
    spots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spots)
    sd.polygon([(-40, -20), (160, -20), (640, horizon), (300, horizon)], fill=(190, 160, 255, 26))
    sd.polygon([(W - 160, -20), (W + 40, -20), (W - 300, horizon), (W - 640, horizon)], fill=(190, 160, 255, 26))
    spots = spots.filter(ImageFilter.GaussianBlur(26))
    img.alpha_composite(spots)
    img.alpha_composite(lay)
    return img.convert("RGB")


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
    reveal = 1.0 if card.get("static") else _ease_out(local_t / 0.5)   # sayac hizli biter (Studio kucuk resmi nihai rakami gostersin); static=true: sayma yok (adim numarasi vb.)
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
        if self.face == "scene3d":
            self.bg = None
            sp = ctx.get("spec3d") or {}
            self.s3_clips = scene3d.Clips(sp.get("set", "studio"))
            self.s3_plan = scene3d.build_plan(ctx["nf"], self.tl, self.cards, self.emos, sp)
        else:
            self.bg = _make_bg_stage() if self.face in ("bot", "robot") else _make_bg()
        self.halo_mask = _radial_mask(1000).point(lambda v: int(v * 0.55))
        self.halo_cache = {}
        self.parts = [tuple(p) for p in ctx["parts"]]
        self.sprites = {s: _radial_mask(s * 4, 1.6) for s in (6, 10, 16)}
        self.tag_font = _font(40)
        self.poses = {int(k): v for k, v in (ctx.get("poses") or {}).items()}


def _scaled(col, f):
    f = min(max(f, 0.0), 1.0)
    return tuple(int(c * f) for c in col)


def _render_one(st, fi):
    t = fi / FPS
    amp = float(st.env[min(fi, len(st.env) - 1)])
    frame = st.bg.copy() if st.bg is not None else None

    if frame is not None:
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
    if st.face == "scene3d":
        clip, cidx = st.s3_plan[fi]
        rgb, vmask, meta = st.s3_clips.frame(clip, cidx)
        base = rgb.copy()
        ftex = _draw_face_led(t, amp, blink, ep, t - s_t0, 0, plate=False).crop((70, 125, 730, 675)).resize((scene3d.TW, scene3d.TH), Image.BOX)
        base = scene3d.draw_face(base, vmask, meta["grid"][cidx], meta["vis"][cidx], ftex, scene3d.FACE["N"])
        frame = Image.fromarray(scene3d.shade(base), "RGB")
    elif st.face == "robot":
        eq = _draw_eq(t, amp)
        frame.paste(eq, (0, 190), eq)
        pose_name = st.poses.get(si) or ("p1" if st.emos[si] in ("happy", "surprised") else "p0")
        in_s = _ease_out((t - s_t0) / 0.35) * (1.0 - _ease_out((t - (s_t0 + tl[si][2] - 0.3)) / 0.3)) if t >= s_t0 else 0.0
        g = 0.0 if pose_name == "p0" else in_s
        w = (1.0 - g, g if pose_name == "p1" else 0.0, g if pose_name == "p2" else 0.0)
        w = (w[0] + w[1] * card_p, w[1] * (1.0 - card_p), w[2])
        spr = _draw_robot(t, amp, blink, ep, t - s_t0, bob, w)
        sc = 1.0 - 0.42 * card_p
        rw, rh = int(spr.width * sc), int(spr.height * sc)
        top = int(100 - 40 * card_p + bob * 0.5 * sc)
        rs = spr.resize((rw, rh), Image.BILINEAR)
        hs = int(1400 * sc)
        hm = st.halo_cache.get(hs)
        if hm is None:
            hm = st.halo_mask.resize((hs, hs))
            st.halo_cache[hs] = hm
        frame.paste(_scaled(ACCENT, 0.30 + 0.40 * amp), (W // 2 - hs // 2, top + int(rh * 0.30) - hs // 2), hm)
        frame.paste(rs, (W // 2 - rw // 2, top), rs)
    elif st.face == "bot":
        eq = _draw_eq(t, amp)
        frame.paste(eq, (0, 190), eq)
        sc = 1.0 - 0.44 * card_p
        bw, bh = int(FW * sc), int(FH * sc)
        top = int(215 - 55 * card_p + bob * 0.8 * sc)
        bs = _draw_bot(t, amp, blink, ep, t - s_t0, bob).resize((bw, bh), Image.BILINEAR)
        hs = int(1250 * sc)
        hm = st.halo_cache.get(hs)
        if hm is None:
            hm = st.halo_mask.resize((hs, hs))
            st.halo_cache[hs] = hm
        frame.paste(_scaled(ACCENT, 0.35 + 0.45 * amp), (W // 2 - hs // 2, top + int(bh * 0.36) - hs // 2), hm)
        frame.paste(bs, (W // 2 - bw // 2, top), bs)
    else:
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
        if st.face == "scene3d":                      # 3B sahne uzerinde okunurluk: koyu cam panel
            back = Image.new("RGBA", (W, 650), (0, 0, 0, 0))
            ImageDraw.Draw(back).rounded_rectangle([46, 6, W - 46, 640], radius=46, fill=(6, 4, 16, int(150 * card_p)),
                                                   outline=ACCENT + (int(120 * card_p),), width=3)
            frame.paste(back, (0, 692), back)
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

    face = spec.get("face", "led")
    set3d = spec.get("set", "studio")
    if face == "scene3d" and not scene3d.set_complete(set3d):
        print(f"[!] 3B sahne '{set3d}' eksik (assets/aura_scenes); 'robot' sprite yuzune dusuluyor", file=sys.stderr)
        face = "robot"
    n_cards_t = {i: tl[i][1] for i in cards_spec if i < len(tl)}
    events = [(0.02, "pop")]
    for i, (_, t0, _) in enumerate(tl):
        if i in cards_spec:
            events.append((max(t0 - 0.05, 0), "whoosh"))
    plan3 = scene3d.build_plan(n_frames, tl, {i: 1 for i in cards_spec}, emos, spec) if face == "scene3d" else None
    if plan3 and plan3[0][0] == "intro":                       # sahneye yuruyus: ayak sesleri (robota yaklastikca guclenir)
        for k, ts_ in enumerate(_walk_step_times()):
            events.append((ts_, "thud", 0.35 + 0.65 * min(ts_ / 3.0, 1.0)))
    final_audio = x + _sfx_track(len(x), events) if sfx else x
    if sfx and face == "scene3d" and spec.get("music", True):
        final_audio = final_audio + _music_track(len(x))
    wav_path = os.path.join(work, "_v2_mix.wav")
    _write_wav(wav_path, final_audio)

    rng = np.random.default_rng(11)
    parts = [[float(rng.uniform(0, W)), float(rng.uniform(0, H)), float(rng.uniform(25, 70)),
              int(rng.choice([6, 10, 16])), float(rng.uniform(0, 6.28))] for _ in range(26)]
    ctx = {"tl": [[s, float(a), float(b)] for s, a, b in tl], "env": [float(v) for v in env_f], "dur": float(dur),
           "tag": spec.get("tag", "AURA  -  AN AI"), "cards": {str(k): v for k, v in cards_spec.items()},
           "emos": emos, "parts": parts, "face": face, "nf": n_frames,
           "spec3d": {"set": set3d, "intro": spec.get("intro", True), "gestures": spec.get("gestures") or {}, "point": spec.get("point", True), "auto_gestures": spec.get("auto_gestures", True)},
           "poses": {str(k): v for k, v in (spec.get("poses") or {}).items()}}

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
        spec = dict(DEMO_SPEC)
        if "--face" in args:
            spec["face"] = args[args.index("--face") + 1]
        make_video_v2(wav, out, DEMO_SCRIPT, spec, sfx=True)
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
