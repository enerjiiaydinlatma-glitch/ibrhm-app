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
from PIL import Image, ImageDraw, ImageFont

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


def _draw_avatar(t, amp, blink, nod):
    """640x640 RGBA (2x cizim, kucultulur)."""
    S2 = 1280
    im = Image.new("RGBA", (S2, S2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S2 // 2
    R = int(400 * (1 + 0.035 * amp))
    # govde: icten disa koyulasan eşmerkezli daireler
    steps = 26
    for i in range(steps):
        f = i / (steps - 1)
        r = int(R * (1 - f * 0.98))
        col = (int(70 + 120 * f), int(34 + 70 * f), int(140 + 115 * f))
        cx, cy = c - int(60 * f), c - int(70 * f) + nod
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (255,))
    # donen halka yaylari
    ang = t * 55 * (1 + 0.9 * amp)
    rr = R + 78
    for k in range(3):
        a0 = ang + k * 120
        d.arc([c - rr, c - rr + nod, c + rr, c + rr + nod], a0, a0 + 52, fill=ACCENT + (200,), width=12)
    # gozler
    eye_w, eye_h = 78, int(112 * max(blink, 0.08))
    ex = 150
    ey = c - 40 + nod
    for sx in (-1, 1):
        x0 = c + sx * ex
        d.rounded_rectangle([x0 - eye_w // 2, ey - eye_h // 2, x0 + eye_w // 2, ey + eye_h // 2],
                            radius=eye_w // 2, fill=(236, 246, 255, 255))
    # agiz: sese gore acilir
    mw = 230
    mh = int(16 + 120 * min(amp * 1.1, 1.0))
    my = c + 190 + nod
    d.rounded_rectangle([c - mw // 2, my - mh // 2, c + mw // 2, my + mh // 2],
                        radius=min(mh // 2, 60), fill=(246, 238, 255, 255))
    return im.resize((640, 640), Image.LANCZOS)


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
def make_video_v2(audio_path, out_path, script_text, spec=None, work_dir=None, sfx=True, progress=None):
    spec = spec or {}
    cards_spec = {int(k): v for k, v in (spec.get("cards") or {}).items()}
    tag = spec.get("tag", "AURA  -  AN AI")
    work = work_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "_video_work")
    os.makedirs(work, exist_ok=True)

    x = _load_audio(audio_path)
    dur = len(x) / SR
    n_frames = int(math.ceil(dur * FPS)) + 1
    env_f = _smooth_env(_envelope(x, FPS))
    env100 = _envelope(x, 100)
    sents = _sentences(script_text)
    tl = _timeline(sents, dur, env100)
    layouts = [_CaptionLayout(s) for s, _, _ in tl]
    wtimes = [_word_times(l.words, t0, d) for l, (s, t0, d) in zip(layouts, tl)]

    # ses efektleri
    events = [(0.02, "pop")]
    for i, (_, t0, _) in enumerate(tl):
        if i in cards_spec:
            events.append((max(t0 - 0.05, 0), "whoosh"))
    final_audio = x
    if sfx:
        final_audio = x + _sfx_track(len(x), events)
    wav_path = os.path.join(work, "_v2_mix.wav")
    _write_wav(wav_path, final_audio)

    bg = _make_bg()
    halo_mask = _radial_mask(1000)
    rng = np.random.default_rng(11)
    parts = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(25, 70), int(rng.choice([6, 10, 16])), rng.uniform(0, 6.28))
             for _ in range(26)]
    sprites = {s: _radial_mask(s * 4, 1.6) for s in (6, 10, 16)}

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", wav_path, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", out_path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    tag_font = _font(40)
    card_t0 = {i: tl[i][1] for i in cards_spec if i < len(tl)}
    card_t1 = {i: tl[i][1] + tl[i][2] for i in cards_spec if i < len(tl)}
    try:
        for fi in range(n_frames):
            t = fi / FPS
            amp = float(env_f[min(fi, len(env_f) - 1)])
            frame = bg.copy()

            # parcaciklar
            for (px, py, sp, sz, ph) in parts:
                y = (py - sp * t) % H
                a = 0.25 + 0.35 * amp + 0.15 * math.sin(t * 1.5 + ph)
                m = sprites[sz].point(lambda v, a=a: int(v * min(max(a, 0), 1)))
                frame.paste(ACCENT, (int(px - sz * 2), int(y - sz * 2)), m)

            # cumle / kart durumu
            si = 0
            for i, (_, t0, d_) in enumerate(tl):
                if t0 <= t < t0 + d_ or (i == len(tl) - 1 and t >= t0):
                    si = i
                    break
            s_t0 = tl[si][1]
            card_i, card_p, card_local = None, 0.0, 0.0
            for i in card_t0:
                p_in = _ease_out((t - card_t0[i]) / 0.35)
                p_out = 1.0 - _ease_out((t - card_t1[i]) / 0.35)
                p = min(p_in, p_out) if t >= card_t0[i] else 0.0
                if p > card_p:
                    card_i, card_p, card_local = i, p, t - card_t0[i]

            # avatar
            blink_phase = (t % 3.4)
            blink = 1.0 - (math.sin(math.pi * blink_phase / 0.16) if blink_phase < 0.16 else 0.0)
            nod = int(-14 * math.exp(-9 * (t - s_t0)) * math.sin(14 * (t - s_t0))) if t - s_t0 < 0.6 else 0
            av = _draw_avatar(t, amp, blink, nod)
            sc = 1.0 - 0.5 * card_p
            cy = 700 - int(330 * card_p)
            avs = av.resize((int(640 * sc), int(640 * sc)), Image.LANCZOS)
            # hale
            hs = int(1000 * sc)
            hm = halo_mask.resize((hs, hs)).point(lambda v: int(v * (0.22 + 0.5 * amp)))
            frame.paste(ACCENT, (W // 2 - hs // 2, cy - hs // 2), hm)
            frame.paste(avs, (W // 2 - avs.width // 2, cy - avs.height // 2), avs)

            # kart
            if card_i is not None and card_p > 0.02:
                lay = _draw_card(cards_spec[card_i], card_local, card_p)
                frame.paste(lay, (0, 700 + int((1 - card_p) * 50)), lay)

            # altyazi
            lay_c = layouts[si]
            d = ImageDraw.Draw(frame)
            wt = wtimes[si]
            active = max([k for k, tw in enumerate(wt) if t >= tw] or [0])
            for k, (xw, yw, w) in enumerate(lay_c.pos):
                if k > active:                  # henuz soylenmeyen kelimeler soluk: kanca 0. karede tam okunur
                    d.text((xw, yw), w, font=lay_c.font, fill=(120, 108, 150), stroke_width=7, stroke_fill=(18, 8, 34))
                    continue
                if k == active:
                    age = t - wt[k]
                    f = lay_c.font  # (pop boyutu kelimeleri birbirine bindirdi: sadece renk vurgusu)
                    col = HILITE
                else:
                    f, col = lay_c.font, WHITE
                d.text((xw, yw), w, font=f, fill=col, stroke_width=7, stroke_fill=(18, 8, 34))

            # ust etiket (AI aciklamasi her karede)
            d.ellipse([60, 92, 78, 110], fill=ACCENT)
            d.text((96, 80), tag, font=tag_font, fill=WHITE, stroke_width=3, stroke_fill=(18, 8, 34))
            d.rectangle([60, 140, 60 + int((W - 120) * min(t / dur, 1)), 146], fill=ACCENT)

            ff.stdin.write(frame.tobytes())
            if progress and fi % 30 == 0:
                progress(fi / n_frames)
    finally:
        try:
            ff.stdin.close()
        except Exception:
            pass
        ff.wait()
    if ff.returncode != 0:
        raise RuntimeError("ffmpeg kodlama hatasi")
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
    if args and args[0] == "--demo":
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
